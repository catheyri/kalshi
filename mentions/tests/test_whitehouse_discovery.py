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

    def test_discover_official_transcript_events_from_sitemap(self):
        sitemap_index = """
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap>
            <loc>https://www.whitehouse.gov/post-sitemap.xml</loc>
          </sitemap>
        </sitemapindex>
        """
        post_sitemap = """
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url>
            <loc>https://www.whitehouse.gov/briefings-statements/2025/01/press-briefing-by-press-secretary-karoline-leavitt/</loc>
            <lastmod>2025-01-29T14:20:46+00:00</lastmod>
          </url>
          <url>
            <loc>https://www.whitehouse.gov/briefings-statements/2025/01/some-other-post/</loc>
            <lastmod>2025-01-25T12:00:00+00:00</lastmod>
          </url>
        </urlset>
        """
        transcript_html = """
        <html>
          <head>
            <meta property="og:title" content="Press Briefing by Press Secretary Karoline Leavitt" />
            <meta property="article:published_time" content="2025-01-29T14:20:46+00:00" />
          </head>
          <body>MS. LEAVITT: Good afternoon.</body>
        </html>
        """

        class StubClient:
            def get_text(self, url):
                mapping = {
                    "https://www.whitehouse.gov/sitemap_index.xml": sitemap_index,
                    "https://www.whitehouse.gov/post-sitemap.xml": post_sitemap,
                    "https://www.whitehouse.gov/briefings-statements/2025/01/press-briefing-by-press-secretary-karoline-leavitt/": transcript_html,
                }
                return mapping[url]

        discovery = WhiteHouseDiscovery(client=StubClient())
        result = discovery.discover_official_transcript_events(start_date="2025-01-20")
        self.assertEqual(len(result.events), 1)
        self.assertEqual(len(result.artifacts), 1)
        self.assertEqual(result.events[0].title, "Press Briefing by Press Secretary Karoline Leavitt")
        self.assertEqual(result.artifacts[0].artifact_type, "official_transcript")
        self.assertEqual(
            result.artifacts[0].uri,
            "https://www.whitehouse.gov/briefings-statements/2025/01/press-briefing-by-press-secretary-karoline-leavitt/",
        )

    def test_discover_official_briefing_video_events_from_sitemap(self):
        sitemap_index = """
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap>
            <loc>https://www.whitehouse.gov/past_event-sitemap.xml</loc>
          </sitemap>
        </sitemapindex>
        """
        past_event_sitemap = """
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url>
            <loc>https://www.whitehouse.gov/videos/press-secretary-karoline-leavitt-briefs-members-of-the-media-jan-28-2025/</loc>
            <lastmod>2025-01-28T18:00:00+00:00</lastmod>
          </url>
          <url>
            <loc>https://www.whitehouse.gov/videos/press-secretary-karoline-leavitt-on-iran/</loc>
            <lastmod>2025-01-28T19:00:00+00:00</lastmod>
          </url>
        </urlset>
        """
        video_html = """
        <html>
          <head>
            <meta property="og:title" content="Press Secretary Karoline Leavitt Briefs Members of the Media, Jan. 28, 2025" />
            <meta property="article:published_time" content="2025-01-28T18:00:00+00:00" />
          </head>
        </html>
        """

        class StubClient:
            def get_text(self, url):
                mapping = {
                    "https://www.whitehouse.gov/sitemap_index.xml": sitemap_index,
                    "https://www.whitehouse.gov/past_event-sitemap.xml": past_event_sitemap,
                    "https://www.whitehouse.gov/videos/press-secretary-karoline-leavitt-briefs-members-of-the-media-jan-28-2025/": video_html,
                }
                return mapping[url]

        discovery = WhiteHouseDiscovery(client=StubClient())
        result = discovery.discover_official_briefing_video_events(start_date="2025-01-20")
        self.assertEqual(len(result.events), 1)
        self.assertEqual(len(result.artifacts), 1)
        self.assertEqual(
            result.events[0].title,
            "Press Secretary Karoline Leavitt Briefs Members of the Media, Jan. 28, 2025",
        )
        self.assertEqual(result.artifacts[0].artifact_type, "video_replay")
        self.assertEqual(
            result.events[0].event_id,
            "whitehouse-videos-press-secretary-karoline-leavitt-briefs-members-of-the-media-jan-28-2025",
        )
        self.assertEqual(result.events[0].actual_start_time, "2025-01-28T18:00:00+00:00")

    def test_discover_official_briefing_video_events_keeps_distinct_urls_with_same_title(self):
        sitemap_index = """
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap>
            <loc>https://www.whitehouse.gov/past_event-sitemap.xml</loc>
          </sitemap>
        </sitemapindex>
        """
        past_event_sitemap = """
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url>
            <loc>https://www.whitehouse.gov/videos/press-secretary-karoline-leavitt-briefs-members-of-the-media-apr-1-2025/</loc>
            <lastmod>2025-04-01T18:00:00+00:00</lastmod>
          </url>
          <url>
            <loc>https://www.whitehouse.gov/videos/press-secretary-karoline-leavitt-briefs-members-of-the-media-apr-1-2025-2/</loc>
            <lastmod>2025-04-01T20:00:00+00:00</lastmod>
          </url>
        </urlset>
        """
        video_html = """
        <html>
          <head>
            <meta property="og:title" content="Press Secretary Karoline Leavitt Briefs Members of the Media, Apr. 1, 2025" />
            <meta property="article:published_time" content="2025-04-01T18:00:00+00:00" />
          </head>
        </html>
        """

        class StubClient:
            def get_text(self, url):
                mapping = {
                    "https://www.whitehouse.gov/sitemap_index.xml": sitemap_index,
                    "https://www.whitehouse.gov/past_event-sitemap.xml": past_event_sitemap,
                    "https://www.whitehouse.gov/videos/press-secretary-karoline-leavitt-briefs-members-of-the-media-apr-1-2025/": video_html,
                    "https://www.whitehouse.gov/videos/press-secretary-karoline-leavitt-briefs-members-of-the-media-apr-1-2025-2/": video_html,
                }
                return mapping[url]

        discovery = WhiteHouseDiscovery(client=StubClient())
        result = discovery.discover_official_briefing_video_events(start_date="2025-01-20")
        self.assertEqual(len(result.events), 2)
        self.assertEqual(
            [event.event_id for event in result.events],
            [
                "whitehouse-videos-press-secretary-karoline-leavitt-briefs-members-of-the-media-apr-1-2025",
                "whitehouse-videos-press-secretary-karoline-leavitt-briefs-members-of-the-media-apr-1-2025-2",
            ],
        )


if __name__ == "__main__":
    unittest.main()
