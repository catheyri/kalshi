import unittest

from mentions_engine.discovery.whitehouse import WhiteHouseDiscovery


class WhiteHouseDiscoveryTests(unittest.TestCase):
    def test_extract_video_links_from_html(self):
        html = """
        <html>
          <body>
            <a href="/videos/press-secretary-karoline-leavitt-briefs-members-of-the-media-mar-30-2026/">
              Press Secretary Karoline Leavitt Briefs Members of the Media, Mar. 30, 2026
            </a>
            March 30, 2026
          </body>
        </html>
        """
        discovery = WhiteHouseDiscovery()
        links = discovery._extract_video_links(html)
        self.assertEqual(len(links), 1)
        self.assertEqual(
            links[0]["url"],
            "https://www.whitehouse.gov/videos/press-secretary-karoline-leavitt-briefs-members-of-the-media-mar-30-2026/",
        )
        self.assertIn("Karoline Leavitt", links[0]["title"])

    def test_discover_events_uses_generic_entrypoint(self):
        html = """
        <html>
          <body>
            <a href="/videos/press-secretary-karoline-leavitt-briefs-members-of-the-media-mar-30-2026/">
              Press Secretary Karoline Leavitt Briefs Members of the Media, Mar. 30, 2026
            </a>
            March 30, 2026
          </body>
        </html>
        """

        class StubClient:
            def get_text(self, url):
                return html

        discovery = WhiteHouseDiscovery(client=StubClient())
        result = discovery.discover_events()
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].event_type, "white_house_press_briefing")


if __name__ == "__main__":
    unittest.main()
