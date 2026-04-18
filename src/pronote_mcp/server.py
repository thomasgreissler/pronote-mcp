from __future__ import annotations

import logging

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .logging_setup import setup_logging
from .tools import register_tools

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

mcp = FastMCP("pronote-mcp")
register_tools(mcp)


def main() -> None:
    logger.info("Starting pronote-mcp server (stdio)")
    mcp.run()


if __name__ == "__main__":
    main()
