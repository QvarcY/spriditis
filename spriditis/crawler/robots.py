from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests


class RobotsCache:
    def __init__(self, session: requests.Session, user_agent: str, timeout: int):
        self.session = session
        self.user_agent = user_agent
        self.timeout = timeout
        self.cache: dict[str, RobotFileParser | None] = {}

    def can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        if base not in self.cache:
            robots_url = f"{base}/robots.txt"
            try:
                response = self.session.get(
                    robots_url,
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                )
                if response.status_code == 200:
                    rp = RobotFileParser()
                    rp.set_url(robots_url)
                    rp.parse(response.text.splitlines())
                    self.cache[base] = rp
                else:
                    self.cache[base] = None
            except requests.RequestException:
                self.cache[base] = None

        rp = self.cache[base]
        return True if rp is None else rp.can_fetch(self.user_agent, url)
