import datetime as dt
import unittest
from meta_sentiment_validator import prospective_window, summarize

T = "2026-10-17T12:00:00+00:00"

def seed(**kw):
    r = dict(published_at_utc="2026-10-17T10:00:00Z",
             first_seen_at_utc="2026-10-17T10:02:00Z",
             authorized_rights="authorized",
             sampling_frame="pre_registered_complete",
             exact_time_verified=True,
             source_pointer="id-a",
             discourse_layer="meta",
             implied_direction="bearish")
    r.update(kw)
    return r

class Tests(unittest.TestCase):
    def test_prospective_prior_message_allowed(self):
        self.assertEqual(len(prospective_window([seed()], T)), 1)
    def test_post_discovered_later_not_backdated(self):
        r=seed(first_seen_at_utc="2026-10-18T10:02:00Z")
        self.assertEqual(len(prospective_window([r], T)), 0)
    def test_post_just_before_cutoff_delayed(self):
        r=seed(published_at_utc="2026-10-17T11:50:00Z",
               first_seen_at_utc="2026-10-17T11:51:00Z")
        self.assertEqual(len(prospective_window([r],T)), 0)
    def test_access_not_approved(self):
        self.assertEqual(len(prospective_window([seed(authorized_rights="unknown")],T)),0)
    def test_event_selected_not_random(self):
        self.assertEqual(len(prospective_window([seed(sampling_frame="search_selected")],T)),0)
    def test_date_only_blocked(self):
        self.assertEqual(len(prospective_window([seed(exact_time_verified=False)],T)),0)
    def test_duplicate_url_counted_once(self):
        self.assertEqual(len(prospective_window([seed(),seed()],T)),1)
    def test_bad_timestamp_order_fail_closed(self):
        with self.assertRaises(ValueError):
            prospective_window([seed(first_seen_at_utc="2026-10-17T09:00:00Z")],T)
    def test_no_timestamps_no_future_claim(self):
        self.assertEqual(len(prospective_window([seed(first_seen_at_utc="")],T)),0)
    def test_no_false_population_inference(self):
        row=dict(case_id="1",platform="reddit_soxl",discourse_layer="meta",
                 meta_type="reputation_revision",implied_direction="neutral",
                 source_precision="date_only",first_seen_at_utc="",
                 forward_eligible="false",probability_sample="false")
        s=summarize([row])
        self.assertFalse(s["population_share_estimable"])
        self.assertEqual(s["forward_eligible"],0)

if __name__=="__main__": unittest.main()
