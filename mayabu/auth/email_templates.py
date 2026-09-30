"""Transactional email templates for Mayabu auth (HTML + plain text)."""

from __future__ import annotations

import html
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmailContent:
    subject: str
    text_body: str
    html_body: str
    kind: str


def _escape(value: str) -> str:
    return html.escape(value or "", quote=True)


def _layout(title: str, intro: str, action_label: str, action_url: str, footer: str) -> str:
    safe_title = _escape(title)
    safe_intro = _escape(intro)
    safe_label = _escape(action_label)
    safe_url = _escape(action_url)
    safe_footer = _escape(footer)
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{safe_title}</title></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#0f172a;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:560px;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:28px;">
        <tr><td style="font-size:20px;font-weight:700;letter-spacing:-0.02em;">Mayabu</td></tr>
        <tr><td style="padding-top:20px;font-size:18px;font-weight:700;">{safe_title}</td></tr>
        <tr><td style="padding-top:12px;font-size:14px;line-height:1.6;color:#475569;">{safe_intro}</td></tr>
        <tr><td style="padding-top:24px;">
          <a href="{safe_url}" style="display:inline-block;background:#1d4ed8;color:#ffffff;text-decoration:none;font-weight:600;font-size:14px;padding:12px 18px;border-radius:8px;">{safe_label}</a>
        </td></tr>
        <tr><td style="padding-top:20px;font-size:12px;line-height:1.5;color:#64748b;">{safe_footer}</td></tr>
        <tr><td style="padding-top:16px;font-size:11px;color:#94a3b8;">If the button does not work, paste this link into your browser:<br>{safe_url}</td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def verification_email(*, to_email: str, verify_url: str, hours: int) -> EmailContent:
    subject = "Verify your Mayabu account"
    text = (
        "Welcome to Mayabu.\n\n"
        f"Verify your email by opening this link:\n{verify_url}\n\n"
        f"This link expires in about {hours} hours.\n"
        "If you did not create an account, you can ignore this message.\n"
    )
    html_body = _layout(
        "Verify your email",
        f"Thanks for joining Mayabu. Confirm {to_email} to finish setting up your account.",
        "Verify email",
        verify_url,
        f"This link expires in about {hours} hours. Mayabu will never ask for your password by email.",
    )
    return EmailContent(subject=subject, text_body=text, html_body=html_body, kind="verification")


def password_reset_email(*, reset_url: str, hours: int) -> EmailContent:
    subject = "Reset your Mayabu password"
    text = (
        "We received a request to reset your Mayabu password.\n\n"
        f"Open this link to choose a new password:\n{reset_url}\n\n"
        f"This link expires in about {hours} hours.\n"
        "If you did not request a reset, you can ignore this message.\n"
    )
    html_body = _layout(
        "Reset your password",
        "Use the button below to choose a new Mayabu password. If you did not request this, you can ignore the email.",
        "Reset password",
        reset_url,
        f"This link expires in about {hours} hours and can be used only once.",
    )
    return EmailContent(subject=subject, text_body=text, html_body=html_body, kind="password_reset")


def password_changed_email() -> EmailContent:
    subject = "Your Mayabu password was changed"
    text = (
        "Your Mayabu password was changed successfully.\n\n"
        "All existing sessions were signed out for your security.\n"
        "If you did not make this change, reset your password again and contact support.\n"
    )
    # No action button required — informational only.
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{_escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#0f172a;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:560px;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:28px;">
        <tr><td style="font-size:20px;font-weight:700;">Mayabu</td></tr>
        <tr><td style="padding-top:20px;font-size:18px;font-weight:700;">Password updated</td></tr>
        <tr><td style="padding-top:12px;font-size:14px;line-height:1.6;color:#475569;">
          Your Mayabu password was changed successfully. All existing sessions were signed out for your security.
          If you did not make this change, reset your password again from the sign-in page.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return EmailContent(subject=subject, text_body=text, html_body=html_body, kind="password_changed")
