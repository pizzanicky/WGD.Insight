import sys
import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import select, and_
from loguru import logger

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Setup paths
project_root = Path(__file__).resolve().parents[1]
media_crawler_root = project_root / "MindSpider" / "DeepSentimentCrawling" / "MediaCrawler"

# Add MediaCrawler to sys.path for its internal imports
if str(media_crawler_root) not in sys.path:
    sys.path.append(str(media_crawler_root))

# Import root config.py using importlib to avoid naming conflict
import importlib.util
config_path = project_root / "config.py"
spec = importlib.util.spec_from_file_location("root_config", config_path)
root_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(root_config)
settings = root_config.settings

# Import database modules
from MindSpider.DeepSentimentCrawling.MediaCrawler.database.db_session import get_session, clear_engine_cache
from MindSpider.DeepSentimentCrawling.MediaCrawler.database.models import WeiboNote

# Import prompt
from DailyDigest.prompts import DAILY_DIGEST_PROMPT

# Import Google Gemini SDK
import google.generativeai as genai

class SimpleLLM:
    """Simple wrapper around Google Gemini API"""
    def __init__(self):
        # Load Google Gemini config from environment
        api_key = os.getenv("GOOGLE_API_KEY")
        model_name = os.getenv("GOOGLE_MODEL_NAME", "gemini-2.0-flash-exp")
        
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not configured in .env file")
        
        # Configure Google Gemini
        genai.configure(api_key=api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name
        
        logger.info(f"[SimpleLLM] Initialized Google Gemini: {model_name}")
    
    def chat(self, prompt: str) -> str:
        """Simple chat interface using Google Gemini"""
        try:
            logger.info(f"[SimpleLLM] Sending request to {self.model_name}")
            
            # Generate content using Gemini
            response = self.model.generate_content(prompt)
            
            # Extract text from response
            if response and response.text:
                logger.info(f"[SimpleLLM] Received response ({len(response.text)} chars)")
                return response.text
            else:
                logger.error("[SimpleLLM] Empty response from Gemini")
                raise ValueError("Empty response from Gemini API")
                
        except Exception as e:
            logger.error(f"[SimpleLLM] Error calling Gemini API: {e}")
            raise

class DailyDigest:
    def __init__(self):
        self.llm = SimpleLLM()

    async def get_recent_posts(self, keyword: str, hours: int = 24):
        """
        Fetch posts for the given keyword from the last N hours.
        """
        try:
            # Calculate time threshold (milliseconds timestamp)
            time_threshold = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
            
            async with get_session() as session:
                if not session:
                    logger.error("Failed to get database session")
                    return []

                # Query WeiboNote (which stores Reddit data)
                # Filter by source_keyword and add_ts (crawled time) or create_time (post time)
                # Using add_ts is safer for "recently crawled"
                stmt = select(WeiboNote).where(
                    and_(
                        WeiboNote.source_keyword == keyword,
                        WeiboNote.add_ts >= time_threshold
                    )
                ).order_by(WeiboNote.add_ts.desc())
                
                result = await session.execute(stmt)
                posts = result.scalars().all()
                
                logger.info(f"Found {len(posts)} posts for keyword '{keyword}' in the last {hours} hours")
                return posts
        except Exception as e:
            logger.exception(f"Error fetching posts: {e}")
            return []

    def format_posts_for_llm(self, posts):
        """
        Format posts into a text string for the LLM.
        保护隐私：不包含用户ID和来源信息
        """
        if not posts:
            return "No posts found."
            
        formatted_text = ""
        for i, post in enumerate(posts[:50]): # 限制到50条帖子避免超过token限制
            # 数据映射: 
            # content -> 标题 + 内容
            # liked_count -> 评分/点赞数
            # comments_count -> 评论数
            # 为保护隐私，不显示作者信息
            
            formatted_text += f"帖子 {i+1}:\n"
            formatted_text += f"内容: {post.content}\n"
            formatted_text += f"互动数据: {post.liked_count}赞, {post.comments_count}评论\n"
            formatted_text += "-" * 20 + "\n"
            
        return formatted_text

    async def generate_digest(self, keyword: str, hours: int = 24):
        """
        Generate the daily digest for the keyword.
        """
        # 1. Fetch posts
        posts = await self.get_recent_posts(keyword, hours)
        
        if not posts:
            return {
                "success": False,
                "message": f"No posts found for keyword '{keyword}' in the last {hours} hours. Please run the crawler first."
            }
            
        # 2. Format for LLM
        posts_text = self.format_posts_for_llm(posts)
        
        # 3. Construct Prompt
        prompt = DAILY_DIGEST_PROMPT.format(keyword=keyword, hours=hours, posts_text=posts_text)
        
        # 4. Call LLM
        try:
            logger.info(f"Generating summary for '{keyword}'...")
            logger.info(f"Prompt length: {len(prompt)} characters")
            
            import time
            start_time = time.time()
            response_text = self.llm.chat(prompt)
            end_time = time.time()
            logger.info(f"LLM call took {end_time - start_time:.2f} seconds")
            
            # Parse JSON from the end
            import json
            import re
            
            summary = response_text
            cover_card_data = {}
            
            try:
                # Find the last JSON object
                # We look for the last '{' which likely starts the JSON
                last_brace_idx = response_text.rfind('{')
                if last_brace_idx != -1:
                    json_text = response_text[last_brace_idx:]
                    # Remove any trailing markdown code block markers
                    json_text = re.sub(r'```\s*$', '', json_text).strip()
                    
                    cover_card_data = json.loads(json_text)
                    summary = response_text[:last_brace_idx].strip()
            except Exception as e:
                logger.warning(f"Failed to parse cover card JSON: {e}")

            return {
                "success": True,
                "summary": summary,
                "cover_card": cover_card_data,
                "post_count": len(posts),
                "top_posts": [
                    {
                        "content": p.content[:100] + "...", 
                        "score": p.liked_count, 
                        "comments": p.comments_count,
                        "url": p.note_url
                    } 
                    for p in sorted(posts, key=lambda x: int(x.liked_count or 0), reverse=True)[:5]
                ]
            }
        except Exception as e:
            logger.exception(f"Error generating summary: {e}")
            return {
                "success": False,
                "message": f"Error generating summary: {str(e)}"
            }

# Helper function for synchronous execution (e.g. from Streamlit)
def run_digest_generation(keyword: str, hours: int = 24):
    # Clear engine cache to avoid "attached to a different loop" error
    # because asyncio.run creates a new loop each time
    clear_engine_cache()
    digest = DailyDigest()
    return asyncio.run(digest.generate_digest(keyword, hours))

if __name__ == "__main__":
    # Test run
    if len(sys.argv) > 1:
        kw = sys.argv[1]
        print(run_digest_generation(kw))
    else:
        print("Please provide a keyword")
