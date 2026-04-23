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


if __name__ == "__main__":
    unittest.main()
