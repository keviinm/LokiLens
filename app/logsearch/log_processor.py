import re
import gzip
import io
from collections import defaultdict
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class LogProcessor:
    @staticmethod
    def extract_container_name(log_line: str) -> str:
        """
        Extract container_name from a log line using regex.
        
        Args:
            log_line: Log line to process
            
        Returns:
            Extracted container name or "Unknown" if not found
        """
        match = re.search(r'"container_name":"([^"]+)"', log_line)
        return match.group(1) if match else "Unknown"

    @staticmethod
    def process_gzipped_logs(file_content: bytes, search_term: str) -> Dict[str, List[str]]:
        """
        Process gzipped log content and search for a specific term.
        
        Args:
            file_content: Gzipped log content as bytes
            search_term: Term to search for in logs
            
        Returns:
            Dictionary of logs grouped by container name
        """
        grouped_logs = defaultdict(list)
        
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(file_content), mode="rb") as gz_file:
                with io.TextIOWrapper(gz_file, encoding="utf-8", errors="replace") as text_file:
                    for line in text_file:
                        if search_term in line:
                            container_name = LogProcessor.extract_container_name(line)
                            grouped_logs[container_name].append(line.strip())
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error in log file: {e}")
        except Exception as e:
            logger.error(f"Error processing log file: {e}")
            
        return grouped_logs 