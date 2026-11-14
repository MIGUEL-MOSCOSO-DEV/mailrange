from pathlib import Path
from tempfile import TemporaryDirectory
from mailrange import inspect

with TemporaryDirectory() as folder:
    eml = Path(folder) / "received.eml"
    eml.write_bytes(
        b"X-MailRange-ID: demo-token\r\n"
        b"Authentication-Results: mx.example.net; spf=pass;\r\n"
        b" dkim=pass; dmarc=pass\r\n\r\n"
    )
    results = inspect(eml, "mx.example.net", "demo-token")
    assert results == {"spf": ["pass"], "dkim": ["pass"], "dmarc": ["pass"]}
    try:
        inspect(eml, "mx.example.net", "different-token")
    except ValueError:
        pass
    else:
        raise AssertionError("Unexpected token accepted")
    print("DEMO | Authentication results from a synthetic EML")
    for method, verdicts in results.items():
        print(f"{method.upper():<8} {', '.join(verdicts)}")
    print("Message correlation: matched")
