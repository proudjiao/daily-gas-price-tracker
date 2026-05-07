import json
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


AAA_STATE_URL = "https://gasprices.aaa.com/?state=CA"
DEFAULT_METRO = "Los Angeles-Long Beach"
DEFAULT_OUTPUT = "data/gas_price.json"
PRICE_CHANGE_THRESHOLD = 0.05


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


def parse_price(price):
    return float(price.replace("$", "").strip())


def format_change(change):
    direction = "above" if change > 0 else "below"
    return f"${abs(change):.3f} {direction}"


def build_recommendation(prices):
    current = parse_price(prices["current"]["regular"])
    yesterday = parse_price(prices["yesterday"]["regular"])
    week_ago = parse_price(prices["week_ago"]["regular"])
    month_ago = parse_price(prices["month_ago"]["regular"])

    comparisons = {
        "vs_yesterday": round(current - yesterday, 3),
        "vs_week_ago": round(current - week_ago, 3),
        "vs_month_ago": round(current - month_ago, 3),
    }

    if (
        comparisons["vs_week_ago"] <= -PRICE_CHANGE_THRESHOLD
        and comparisons["vs_month_ago"] <= -PRICE_CHANGE_THRESHOLD
    ):
        status = "low"
    elif (
        comparisons["vs_week_ago"] >= PRICE_CHANGE_THRESHOLD
        and comparisons["vs_month_ago"] >= PRICE_CHANGE_THRESHOLD
    ):
        status = "high"
    else:
        status = "normal"

    trending_up = (
        comparisons["vs_yesterday"] > 0
        and comparisons["vs_week_ago"] >= PRICE_CHANGE_THRESHOLD
        and comparisons["vs_month_ago"] >= PRICE_CHANGE_THRESHOLD
    )
    trend = "trending_up" if trending_up else "mixed"

    if status == "low" or trending_up:
        action = "gas_today"
    elif status == "high" and comparisons["vs_yesterday"] <= 0:
        action = "wait_if_possible"
        trend = "easing"
    else:
        action = "neutral"

    reason = (
        f"Regular is {format_change(comparisons['vs_week_ago'])} last week "
        f"and {format_change(comparisons['vs_month_ago'])} last month."
    )

    if status == "low":
        summary = (
            "Prices are low versus recent averages, so today is a good day to "
            "fill up."
        )
    elif trending_up:
        summary = (
            "Prices are high and trending up, so filling today is safer if you "
            "need gas soon."
        )
    else:
        summaries = {
            "wait_if_possible": (
                "Prices are high and not rising today, so waiting is reasonable "
                "if your tank is not low."
            ),
            "neutral": "Prices are mixed or normal, so buy only if you need gas.",
        }
        summary = summaries[action]

    return {
        "fuel_type": "regular",
        "status": status,
        "trend": trend,
        "action": action,
        "summary": summary,
        "reason": reason,
        "comparisons": comparisons,
    }


def format_label(value):
    return value.replace("_", " ").title()


def format_signed_change(value):
    if value > 0:
        return f"+${value:.3f}"
    if value < 0:
        return f"-${abs(value):.3f}"
    return "$0.000"


def describe_change(value):
    if value > 0:
        return "higher"
    if value < 0:
        return "lower"
    return "flat"


def trend_indicator(value):
    if value > 0:
        return {"arrow": "↑", "color": "#dc2626", "label": "higher"}
    if value < 0:
        return {"arrow": "↓", "color": "#16a34a", "label": "lower"}
    return {"arrow": "→", "color": "#64748b", "label": "flat"}


def recommendation_theme(action):
    themes = {
        "gas_today": {
            "accent": "#f97316",
            "accent_dark": "#c2410c",
            "background": "#fff7ed",
            "border": "#fed7aa",
            "label": "Gas Today",
        },
        "wait_if_possible": {
            "accent": "#2563eb",
            "accent_dark": "#1d4ed8",
            "background": "#eff6ff",
            "border": "#bfdbfe",
            "label": "Wait If Possible",
        },
        "neutral": {
            "accent": "#475569",
            "accent_dark": "#334155",
            "background": "#f8fafc",
            "border": "#cbd5e1",
            "label": "Neutral",
        },
    }
    return themes.get(action, themes["neutral"])


def build_result():
    metro = os.getenv("GAS_PRICE_METRO", DEFAULT_METRO)
    html = fetch_page(AAA_STATE_URL)
    lines = parse_text_lines(html)
    prices = parse_metro_prices(lines, metro)

    return {
        "source": AAA_STATE_URL,
        "metro": metro,
        "price_as_of": first_price_date(lines),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "prices": prices,
        "recommendation": build_recommendation(prices),
    }


def build_email_body(result):
    current = result["prices"]["current"]
    recommendation = result["recommendation"]
    comparisons = recommendation["comparisons"]
    return (
        f"Recommendation: {format_label(recommendation['action'])}\n"
        f"Status: {format_label(recommendation['status'])}, "
        f"{format_label(recommendation['trend'])}\n"
        f"Regular: {current['regular']}\n"
        f"Reason: {recommendation['reason']}\n"
        f"{recommendation['summary']}\n\n"
        "Trend check:\n"
        f"- vs yesterday: {format_signed_change(comparisons['vs_yesterday'])} "
        f"{describe_change(comparisons['vs_yesterday'])}\n"
        f"- vs last week: {format_signed_change(comparisons['vs_week_ago'])} "
        f"{describe_change(comparisons['vs_week_ago'])}\n"
        f"- vs last month: {format_signed_change(comparisons['vs_month_ago'])} "
        f"{describe_change(comparisons['vs_month_ago'])}\n\n"
        "How we decide:\n"
        f"- High: regular is at least ${PRICE_CHANGE_THRESHOLD:.2f} above both "
        "last week and last month.\n"
        f"- Low: regular is at least ${PRICE_CHANGE_THRESHOLD:.2f} below both "
        "last week and last month.\n"
        "- Trending up: regular is above yesterday, last week, and last month, "
        "with week/month moves above the threshold.\n\n"
        f"Daily gas price update for {result['metro']}\n\n"
        f"Regular: {current['regular']}\n"
        f"Mid-grade: {current['mid_grade']}\n"
        f"Premium: {current['premium']}\n"
        f"Diesel: {current['diesel']}\n\n"
        f"AAA price as of: {result['price_as_of']}\n"
        f"Source: {result['source']}\n"
        f"Location: {result['metro']}\n"
    )


def build_price_card(label, price, accent=False):
    border = "#f97316" if accent else "#e2e8f0"
    background = "#fff7ed" if accent else "#ffffff"
    caption = "Recommendation fuel" if accent else "AAA average"
    return f"""
        <td style="width:50%;padding:6px;">
          <div style="border:1px solid {border};background:{background};border-radius:16px;padding:14px;">
            <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.06em;">{escape(label)}</div>
            <div style="font-size:26px;font-weight:800;color:#0f172a;line-height:1.2;">{escape(price)}</div>
            <div style="font-size:12px;color:#64748b;">{caption}</div>
          </div>
        </td>
    """


def build_trend_row(label, value):
    indicator = trend_indicator(value)
    return f"""
      <tr>
        <td style="padding:10px 0;border-bottom:1px solid #e2e8f0;color:#334155;font-size:14px;">{escape(label)}</td>
        <td style="padding:10px 0;border-bottom:1px solid #e2e8f0;text-align:right;font-size:14px;">
          <span style="color:{indicator['color']};font-weight:800;font-size:18px;">{indicator['arrow']}</span>
          <span style="font-weight:800;color:#0f172a;">{format_signed_change(value)}</span>
          <span style="color:#64748b;">{indicator['label']}</span>
        </td>
      </tr>
    """


def build_flow_step(label):
    return f"""
      <div style="border:1px solid #cbd5e1;background:#ffffff;border-radius:14px;padding:10px 12px;text-align:center;font-size:13px;font-weight:700;color:#0f172a;">
        {escape(label)}
      </div>
    """


def build_email_html(result):
    current = result["prices"]["current"]
    recommendation = result["recommendation"]
    comparisons = recommendation["comparisons"]
    theme = recommendation_theme(recommendation["action"])
    preheader = (
        f"{theme['label']}: regular is {current['regular']} and "
        f"{format_label(recommendation['trend']).lower()} in {result['metro']}."
    )

    return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{escape(preheader)}</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f1f5f9;padding:24px 0;">
      <tr>
        <td align="center" style="padding:0 12px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border-radius:24px;overflow:hidden;border:1px solid #e2e8f0;">
            <tr>
              <td style="padding:26px;background:{theme['background']};border-bottom:1px solid {theme['border']};">
                <div style="font-size:13px;font-weight:800;color:{theme['accent_dark']};letter-spacing:0.08em;text-transform:uppercase;">⛽ Today's Gas Call</div>
                <div style="font-size:42px;line-height:1.05;font-weight:900;color:{theme['accent_dark']};margin-top:8px;">{escape(theme['label'])}</div>
                <div style="font-size:17px;line-height:1.5;color:#334155;margin-top:12px;">{escape(recommendation['summary'])}</div>
                <div style="margin-top:18px;padding:12px 14px;background:#ffffff;border:1px solid {theme['border']};border-radius:16px;">
                  <span style="font-size:13px;color:#64748b;">Regular now</span>
                  <span style="font-size:26px;font-weight:900;color:#0f172a;margin-left:8px;">{escape(current['regular'])}</span>
                  <span style="font-size:13px;color:#64748b;margin-left:8px;">{escape(format_label(recommendation['status']))}, {escape(format_label(recommendation['trend']))}</span>
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:22px 24px 4px;">
                <div style="font-size:13px;color:#64748b;">📍 {escape(result['metro'])}</div>
                <div style="font-size:13px;color:#64748b;margin-top:4px;">🗓 AAA price as of: {escape(result['price_as_of'])}</div>
              </td>
            </tr>

            <tr>
              <td style="padding:20px 18px 4px;">
                <div style="font-size:18px;font-weight:900;color:#0f172a;margin:0 6px 8px;">📊 Price Snapshot</div>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    {build_price_card("Regular", current["regular"], True)}
                    {build_price_card("Mid-grade", current["mid_grade"])}
                  </tr>
                  <tr>
                    {build_price_card("Premium", current["premium"])}
                    {build_price_card("Diesel", current["diesel"])}
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding:20px 24px;">
                <div style="font-size:18px;font-weight:900;color:#0f172a;margin-bottom:8px;">🧭 Trend Check</div>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                  {build_trend_row("vs yesterday", comparisons["vs_yesterday"])}
                  {build_trend_row("vs last week", comparisons["vs_week_ago"])}
                  {build_trend_row("vs last month", comparisons["vs_month_ago"])}
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding:0 24px 22px;">
                <div style="border:1px solid #e2e8f0;background:#f8fafc;border-radius:20px;padding:18px;">
                  <div style="font-size:18px;font-weight:900;color:#0f172a;margin-bottom:10px;">🧪 How We Decide</div>
                  {build_flow_step("Start with regular gas")}
                  <div style="text-align:center;color:#94a3b8;font-size:22px;line-height:1.3;">↓</div>
                  {build_flow_step("Compare against yesterday, last week, and last month")}
                  <div style="text-align:center;color:#94a3b8;font-size:22px;line-height:1.3;">↓</div>
                  {build_flow_step(f"High if week and month are both +${PRICE_CHANGE_THRESHOLD:.2f} or more")}
                  <div style="text-align:center;color:#94a3b8;font-size:22px;line-height:1.3;">↓</div>
                  {build_flow_step("Gas Today if price is low or clearly trending up")}
                  <p style="font-size:14px;line-height:1.55;color:#334155;margin:14px 0 0;">
                    Today's reason: <strong>{escape(recommendation['reason'])}</strong>
                  </p>
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:0 24px 24px;">
                <div style="border-radius:18px;background:#0f172a;color:#e2e8f0;padding:16px;">
                  <div style="font-size:15px;font-weight:900;color:#ffffff;">Why this matters</div>
                  <div style="font-size:14px;line-height:1.5;margin-top:6px;">
                    Waiting can be risky when the price is already above recent averages and still moving up. This is the Los Angeles-Long Beach metro average, not station-level pricing.
                  </div>
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 24px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:12px;line-height:1.5;color:#64748b;">
                Source: <a href="{escape(result['source'])}" style="color:{theme['accent_dark']};">AAA California gas prices</a><br>
                Location: {escape(result['metro'])}<br>
                Fetched at: {escape(result['fetched_at'])}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


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
    current_regular = result["prices"]["current"]["regular"]
    action_label = format_label(result["recommendation"]["action"])

    message = EmailMessage()
    message["Subject"] = f"{action_label}: Regular {current_regular} in {result['metro']}"
    message["From"] = email_from
    message["To"] = required["EMAIL_TO"]
    message.set_content(build_email_body(result))
    message.add_alternative(build_email_html(result), subtype="html")

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
