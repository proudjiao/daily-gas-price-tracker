import json
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


AAA_STATE_URL = "https://gasprices.aaa.com/?state=CA"
DEFAULT_METRO = "Los Angeles-Long Beach"
DEFAULT_OUTPUT = "data/gas_price.json"


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def fetch_page(url):
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_text_lines(html):
    parser = TextParser()
    parser.feed(html)
    return "\n".join(parser.parts).splitlines()


def first_price_date(lines):
    for line in lines:
        if line.startswith("Price as of"):
            return line.replace("Price as of", "").strip()
    raise ValueError("Could not find AAA price date")


def parse_metro_prices(lines, metro):
    start = lines.index(metro)
    labels = {
        "Current Avg.": "current",
        "Yesterday Avg.": "yesterday",
        "Week Ago Avg.": "week_ago",
        "Month Ago Avg.": "month_ago",
        "Year Ago Avg.": "year_ago",
    }

    prices = {}
    for label, key in labels.items():
        label_index = next(i for i in range(start, len(lines)) if lines[i] == label)
        regular, mid_grade, premium, diesel = lines[label_index + 1 : label_index + 5]
        prices[key] = {
            "regular": regular,
            "mid_grade": mid_grade,
            "premium": premium,
            "diesel": diesel,
        }

    return prices


def build_result():
    metro = os.getenv("GAS_PRICE_METRO", DEFAULT_METRO)
    html = fetch_page(AAA_STATE_URL)
    lines = parse_text_lines(html)

    return {
        "source": AAA_STATE_URL,
        "zip": os.getenv("GAS_PRICE_ZIP", "90048"),
        "zip_proxy": os.getenv(
            "GAS_PRICE_ZIP_PROXY",
            "90048 -> Los Angeles-Long Beach metro average",
        ),
        "metro": metro,
        "price_as_of": first_price_date(lines),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "prices": parse_metro_prices(lines, metro),
    }


def build_email_body(result):
    current = result["prices"]["current"]
    return (
        f"Daily gas price update for {result['zip']} "
        f"({result['metro']} metro average)\n\n"
        f"Regular: {current['regular']}\n"
        f"Mid-grade: {current['mid_grade']}\n"
        f"Premium: {current['premium']}\n"
        f"Diesel: {current['diesel']}\n\n"
        f"AAA price as of: {result['price_as_of']}\n"
        f"Source: {result['source']}\n"
        f"Note: {result['zip_proxy']}\n"
    )


def send_email(result):
    required = {
        "SMTP_HOST": os.getenv("SMTP_HOST"),
        "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
        "EMAIL_TO": os.getenv("EMAIL_TO"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        print(f"Skipping email; missing environment variables: {', '.join(missing)}")
        return

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    email_from = os.getenv("EMAIL_FROM", required["SMTP_USERNAME"])

    message = EmailMessage()
    message["Subject"] = (
        f"Gas price update: regular {result['prices']['current']['regular']}"
    )
    message["From"] = email_from
    message["To"] = required["EMAIL_TO"]
    message.set_content(build_email_body(result))

    with smtplib.SMTP(required["SMTP_HOST"], smtp_port, timeout=30) as server:
        server.starttls()
        server.login(required["SMTP_USERNAME"], required["SMTP_PASSWORD"])
        server.send_message(message)

    print(f"Sent gas price email to {required['EMAIL_TO']}")


def main():
    output_path = Path(os.getenv("GAS_PRICE_OUTPUT", DEFAULT_OUTPUT))
    result = build_result()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

    if os.getenv("SEND_EMAIL", "").lower() in {"1", "true", "yes"}:
        send_email(result)


if __name__ == "__main__":
    main()
