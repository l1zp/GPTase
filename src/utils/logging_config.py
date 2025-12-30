"""
Debug logging configuration for OpenAI API
"""

import logging
import sys

def setup_debug_logging():
    """Setup detailed logging for debugging OpenAI API issues."""
    
    # Set root logger to DEBUG level
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('openai_debug.log')
        ]
    )
    
    # Enable detailed logging for OpenAI client
    openai_logger = logging.getLogger('openai')
    openai_logger.setLevel(logging.DEBUG)
    
    # Enable detailed logging for httpx (used by OpenAI client)
    httpx_logger = logging.getLogger('httpx')
    httpx_logger.setLevel(logging.DEBUG)
    
    # Enable detailed logging for httpcore (lower level HTTP)
    httpcore_logger = logging.getLogger('httpcore')
    httpcore_logger.setLevel(logging.DEBUG)
    
    # Enable detailed logging for our providers
    providers_logger = logging.getLogger('src.models.providers')
    providers_logger.setLevel(logging.DEBUG)
    
    # Log all HTTP requests and responses
    logging.getLogger('openai._base_client').setLevel(logging.DEBUG)
    logging.getLogger('openai._client').setLevel(logging.DEBUG)
    
    print("=" * 80)
    print("Debug logging enabled!")
    print("=" * 80)
    print("Log levels:")
    print(f"  - openai: {openai_logger.getEffectiveLevel()}")
    print(f"  - httpx: {httpx_logger.getEffectiveLevel()}")
    print(f"  - httpcore: {httpcore_logger.getEffectiveLevel()}")
    print(f"  - src.models.providers: {providers_logger.getEffectiveLevel()}")
    print("=" * 80)
    print("Logs will be written to:")
    print("  - Console (stdout)")
    print("  - openai_debug.log file")
    print("=" * 80)


def setup_info_logging():
    """Setup INFO level logging for normal operation."""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set OpenAI to INFO level to see retry messages
    openai_logger = logging.getLogger('openai')
    openai_logger.setLevel(logging.INFO)
    
    # Set httpx to WARNING to reduce noise
    httpx_logger = logging.getLogger('httpx')
    httpx_logger.setLevel(logging.WARNING)
    
    # Set httpcore to WARNING to reduce noise
    httpcore_logger = logging.getLogger('httpcore')
    httpcore_logger.setLevel(logging.WARNING)
    
    # Set providers to INFO
    providers_logger = logging.getLogger('src.models.providers')
    providers_logger.setLevel(logging.INFO)
    
    print("=" * 80)
    print("Info logging enabled!")
    print("=" * 80)


if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup logging for debugging')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG level logging')
    parser.add_argument('--info', action='store_true', help='Enable INFO level logging')
    
    args = parser.parse_args()
    
    if args.debug:
        setup_debug_logging()
    elif args.info:
        setup_info_logging()
    else:
        print("Please specify --debug or --info")
