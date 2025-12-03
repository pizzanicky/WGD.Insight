import sys
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "MindSpider/DeepSentimentCrawling/MediaCrawler"))

# Mock dependencies
sys.modules['config'] = MagicMock()
sys.modules['config'].CRAWLER_MAX_NOTES_COUNT = 10
sys.modules['db_config'] = MagicMock()
sys.modules['playwright'] = MagicMock()
sys.modules['playwright.async_api'] = MagicMock()
sys.modules['playwright.async_api'] = MagicMock()
sys.modules['httpx'] = MagicMock()
sys.modules['loguru'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['cv2'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['aiomysql'] = MagicMock()
sys.modules['tenacity'] = MagicMock()

# Mock database modules
sys.modules['database'] = MagicMock()
sys.modules['database.models'] = MagicMock()
sys.modules['database.db_utils'] = MagicMock()

# Define mock WeiboNote
class MockWeiboNote:
    def __init__(self):
        self.note_id = None
        self.content = None
        self.source_keyword = None

sys.modules['database.models'].WeiboNote = MockWeiboNote

try:
    from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit.core import RedditCrawler
    from MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit.client import RedditClient
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

class TestRedditCrawler(unittest.TestCase):
    def test_id_conversion(self):
        """Test Base36 to Base10 conversion logic"""
        # Test case: t3_xyz -> xyz -> int
        reddit_id = "t3_xyz"
        clean_id = reddit_id.split('_')[-1]
        int_id = int(clean_id, 36)
        self.assertEqual(int_id, 44027) # xyz in base36 is 44027
        
        # Test case: 123 -> 123 -> int
        reddit_id_2 = "123"
        int_id_2 = int(reddit_id_2, 36)
        self.assertEqual(int_id_2, 1371) # 123 in base36 is 1*36^2 + 2*36 + 3 = 1296 + 72 + 3 = 1371

    @patch('MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit.core.RedditCrawler._save_note', new_callable=AsyncMock)
    def test_search_and_mapping(self, mock_save):
        """Test search flow and data mapping"""
        crawler = RedditCrawler()
        
        # Mock search response
        mock_response = {
            'data': {
                'children': [
                    {
                        'data': {
                            'id': 't3_xyz',
                            'title': 'Test Title',
                            'selftext': 'Test Content',
                            'created_utc': 1600000000,
                            'ups': 100,
                            'num_comments': 50,
                            'author': 'test_user',
                            'permalink': '/r/test/comments/xyz/test_title/'
                        }
                    }
                ]
            }
        }
        
        # Patch the instance method directly
        crawler.client.search = AsyncMock(return_value=mock_response)
        
        # Run search
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run search
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Patch source_keyword_var in the core module where it's imported
        with patch('MindSpider.DeepSentimentCrawling.MediaCrawler.media_platform.reddit.core.source_keyword_var') as mock_var:
            mock_var.get.return_value = "TSLA"
            loop.run_until_complete(crawler.search())
            
        # Verify save was called
        self.assertTrue(mock_save.called)
        
        # Verify mapped data
        saved_note = mock_save.call_args[0][0]
        self.assertEqual(saved_note.note_id, "44027") # xyz -> 44027
        self.assertEqual(saved_note.content, "Test Title\nTest Content")
        self.assertEqual(saved_note.source_keyword, "TSLA")

if __name__ == '__main__':
    unittest.main()
