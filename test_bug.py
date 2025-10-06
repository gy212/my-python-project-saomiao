import unittest
import os
import sys
import tempfile
import base64

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.main_api import Api

class TestBug(unittest.TestCase):
    def setUp(self):
        self.api = Api()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Clean up the created temp directory and any files
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_directory_traversal_vulnerability(self):
        # Create a controlled temporary environment
        base_dir = self.temp_dir
        safe_zone = os.path.join(base_dir, "safe_zone")
        os.makedirs(safe_zone)

        # The payload will try to traverse from safe_zone to base_dir
        malicious_filename = os.path.join("..", "exploit.png")
        file_content = base64.b64encode(b"exploit").decode('utf-8')

        file_data = [{
            'name': malicious_filename,
            'data': f"data:image/png;base64,{file_content}"
        }]

        # Mock tempfile.mkdtemp to return our controlled "safe_zone"
        original_mkdtemp = tempfile.mkdtemp
        tempfile.mkdtemp = lambda prefix: safe_zone

        self.api.upload_files(file_data)

        # Restore the original function
        tempfile.mkdtemp = original_mkdtemp

        # Check if the file was created outside the safe_zone, in the base_dir
        exploit_path = os.path.join(base_dir, "exploit.png")
        self.assertFalse(os.path.exists(exploit_path), f"Vulnerability exploited! File created at {exploit_path}")

if __name__ == '__main__':
    unittest.main()