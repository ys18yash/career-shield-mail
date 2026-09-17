import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.security_sanitizer import sanitize_email_text, extract_safe_urls

def test_xss_and_html_injection():
    malicious_html = """
    <html>
        <body>
            <script>alert('pwned');</script>
            <iframe src="javascript:alert(1)"></iframe>
            <a href="javascript:stealCookie()">Click for job</a>
            <p>We are offering <b>₹50,000</b> monthly stipend. <img src="x" onerror="steal()"></p>
        </body>
    </html>
    """
    clean = sanitize_email_text(malicious_html)
    assert "<script>" not in clean
    assert "<iframe>" not in clean
    assert "javascript:" not in clean
    assert "onerror=" not in clean
    assert "50,000 monthly stipend" in clean
    print("  [PASS] HTML & XSS Injection Sanitization Test")

def test_oversized_payload_truncation():
    giant_text = "A" * 100000
    clean = sanitize_email_text(giant_text, max_chars=10000)
    assert len(clean) == 10000
    print("  [PASS] Oversized Payload Truncation Test")

def test_safe_url_extraction():
    text_with_links = """
    Check careers at https://careers.google.com/jobs and http://amazon.jobs.
    Do not open javascript:alert(1) or data:text/html,malicious.
    """
    urls = extract_safe_urls(text_with_links)
    assert "https://careers.google.com/jobs" in urls
    assert "http://amazon.jobs" in urls
    assert not any("javascript:" in u for u in urls)
    assert not any("data:" in u for u in urls)
    print("  [PASS] Safe URL Extraction Test")

if __name__ == "__main__":
    print("RUNNING SECURITY HARDENING TESTS")
    test_xss_and_html_injection()
    test_oversized_payload_truncation()
    test_safe_url_extraction()
    print("ALL SECURITY HARDENING TESTS PASSED.")
