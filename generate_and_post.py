#!/usr/bin/env python3
"""
Daily LINE AI post bot.
- Picks today's theme (weekday-based, Asia/Bangkok time)
- Generates a fresh Thai post with Google Gemini (free tier)
- Pushes it into a LINE group via the Messaging API

Runs on GitHub Actions daily. No external pip packages required (uses urllib).
Required environment variables (set as GitHub Actions secrets):
  GEMINI_API_KEY               - Google AI Studio API key
  LINE_CHANNEL_ACCESS_TOKEN    - LINE Messaging API channel access token
  LINE_GROUP_ID                - The target LINE group ID
"""

import os
import sys
import json
import datetime
import urllib.request
import urllib.error

# --- Config -----------------------------------------------------------------

GEMINI_MODEL = "gemini-2.5-flash"  # free tier; change if needed

# weekday(): Monday=0 ... Sunday=6
THEMES = {
    0: ("📰 ข่าว AI ประจำสัปดาห์",
        "สรุปข่าว AI ที่น่าสนใจล่าสุด 2-3 ข่าว แบบสั้น กระชับ เข้าใจง่าย เหมาะกับคนทั่วไป "
        "ถ้าอ้างอิงข่าว ให้ใส่ชื่อแหล่งข่าวสั้นๆ ต่อท้าย ลงท้ายด้วยคำถามชวนคุย"),
    1: ("🛠️ เครื่องมือ AI แนะนำ",
        "แนะนำเครื่องมือ AI 1 ตัวที่น่าสนใจ บอกว่าใช้ทำอะไร ดียังไง และเริ่มใช้ยังไง "
        "ลงท้ายด้วยคำถามว่าใครเคยใช้ตัวไหนบ้าง"),
    2: ("💬 คำถามชวนคุย",
        "ตั้งคำถามปลายเปิด 1 ข้อเกี่ยวกับการใช้ AI ในชีวิตประจำวันหรือการทำงาน "
        "เพื่อให้สมาชิกมาแชร์ประสบการณ์กัน เนื้อหาสั้นๆ"),
    3: ("🎯 Prompt เด็ดประจำวัน",
        "แจก prompt ที่ใช้ได้จริง 1 อัน พร้อมตัวอย่างสั้นๆ และวิธีปรับใช้ "
        "ลงท้ายด้วยชวนให้ลองแล้วมาแชร์ผลลัพธ์"),
    4: ("🧩 เคสจริง / รีวิวการใช้ AI",
        "เล่าเคสตัวอย่างการใช้ AI แก้ปัญหาจริง หรือรีวิวการใช้งานเครื่องมือ AI "
        "ให้เห็นภาพและเอาไปปรับใช้ได้จริง"),
    5: ("📚 AI 101",
        "อธิบายศัพท์หรือแนวคิด AI พื้นฐาน 1 เรื่อง เช่น LLM, token, RAG, prompt, fine-tuning "
        "แบบเข้าใจง่ายสำหรับมือใหม่ พร้อมตัวอย่างเปรียบเทียบ"),
    6: ("🎉 โพล / คุยเล่นวันอาทิตย์",
        "ตั้งโพลหรือหัวข้อสนุกๆ เกี่ยวกับ AI ให้สมาชิกโหวตหรือตอบเล่นๆ "
        "ใส่ตัวเลือกให้โหวตง่ายๆ 3-4 ตัวเลือก"),
}


def today_bangkok():
    """Return current datetime in Asia/Bangkok (UTC+7) without external deps."""
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))


def build_prompt(theme_title, theme_brief, date_str, include_links):
    link_rule = (
        "- แนบลิงก์แหล่งข้อมูล/ข่าวจริงต่อท้ายแต่ละหัวข้อ (ขึ้นบรรทัดใหม่ ใช้ URL เต็ม "
        "ที่เข้าถึงได้จริงจากผลการค้นหา ห้ามแต่ง URL ขึ้นเอง) ถ้าไม่มั่นใจว่าลิงก์มีจริง "
        "ให้ระบุแค่ชื่อแหล่งข่าวแทน\n"
        if include_links else ""
    )
    length_rule = (
        "- เขียนให้มีเนื้อหาพอสมควร ประมาณ 14-22 บรรทัด แบ่งเป็นหัวข้อย่อย 2-3 หัวข้อ "
        "พร้อมคำอธิบายสั้นๆ ในแต่ละหัวข้อ\n"
        if include_links else
        "- เขียนให้มีเนื้อหาพอสมควร ประมาณ 10-16 บรรทัด อ่านง่ายบนมือถือ\n"
    )
    return (
        f"คุณเป็นแอดมินของกลุ่ม LINE ชื่อ \"AI community by ENPine\" "
        f"ซึ่งเป็นชุมชนคนไทยที่สนใจเรื่อง AI ทั้งมือใหม่และมือโปร\n\n"
        f"วันนี้คือ {date_str} ธีมของวันนี้คือ: {theme_title}\n"
        f"สิ่งที่ต้องทำ: {theme_brief}\n\n"
        f"เขียนโพสต์ภาษาไทย 1 โพสต์ พร้อมโพสต์ลงกลุ่มได้ทันที โดย:\n"
        f"- ขึ้นต้นด้วยหัวข้อ \"{theme_title}\" และวันที่\n"
        f"{length_rule}"
        f"{link_rule}"
        f"- ใช้ภาษาเป็นกันเอง เป็นมิตร ให้ข้อมูลที่เอาไปใช้ได้จริง\n"
        f"- โทนการเขียน: เขียนแบบคนคุยกันจริงๆ เป็นประโยคที่ไหลลื่น สุภาพ สงบ ไม่หวือหวา "
        f"เน้นเนื้อหาและความเข้าใจมากกว่าลูกเล่น\n"
        f"- ใช้อิโมจิได้เฉพาะที่หัวข้อหลักตอนต้นเท่านั้น ห้ามใส่อิโมจิแทรกในเนื้อหาหรือทุกบรรทัด\n"
        f"- ห้ามใช้อิโมจิตัวเลข (เช่น 1️⃣ 2️⃣) ให้ใช้ตัวเลขธรรมดา 1) 2) แทน\n"
        f"- หลีกเลี่ยงคำอุทานเว่อร์ๆ เช่น สุดๆ ร้อนแรง ตื่นเต้นสุดๆ ปังมาก และเครื่องหมายตกใจซ้ำๆ\n"
        f"- ลงท้ายด้วยคำถามหรือคำชวนให้สมาชิกมีส่วนร่วมแบบเรียบๆ 1 ประโยค\n"
        f"- ห้ามใส่เครื่องหมาย markdown เช่น ** หรือ ``` ให้ส่งเป็นข้อความธรรมดาที่ก็อปวางลง LINE ได้เลย\n"
        f"- ตอบกลับมาเฉพาะตัวโพสต์ ไม่ต้องมีคำอธิบายอื่น"
    )


def call_gemini(prompt, use_search):
    api_key = os.environ["GEMINI_API_KEY"]
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if use_search:
        # Google Search grounding for fresher news (supported on gemini-2.0-flash)
        body["tools"] = [{"google_search": {}}]

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Gemini response: {json.dumps(payload)[:800]}") from e

    if not text:
        raise RuntimeError("Gemini returned empty text.")
    return text


def clean_text(text):
    # Strip accidental code fences / stray markdown bold
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text.replace("**", "")


def push_to_line(text):
    token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    group_id = os.environ["LINE_GROUP_ID"]
    url = "https://api.line.me/v2/bot/message/push"
    body = {"to": group_id, "messages": [{"type": "text", "text": text[:4900]}]}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def main():
    now = today_bangkok()
    weekday = now.weekday()
    date_str = now.strftime("%A %d %B %Y")
    theme_title, theme_brief = THEMES[weekday]
    # news + tools + AI-101 days: search the web and include real source links
    include_links = weekday in (0, 1, 5)
    use_search = include_links

    print(f"[info] Bangkok time: {now.isoformat()}  weekday={weekday}")
    print(f"[info] Theme: {theme_title}  (search={use_search}, links={include_links})")

    prompt = build_prompt(theme_title, theme_brief, date_str, include_links)
    text = clean_text(call_gemini(prompt, use_search))
    print("[info] Generated post:\n" + text)

    status = push_to_line(text)
    print(f"[info] LINE push status: {status}")
    print("[done] Posted successfully.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")
        print(f"[error] HTTP {e.code}: {detail}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa
        print(f"[error] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
