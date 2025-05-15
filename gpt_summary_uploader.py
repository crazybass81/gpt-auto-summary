import os
import time
import glob
import requests
from requests.auth import HTTPBasicAuth
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from openai import OpenAI

# ===== 설정 =====
ICLOUD_PATH = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/GPTConnect")
NAS_URL = "https://192.168.35.190:5006"
USERNAME = "T_GPT"
PASSWORD = "Tothetop01!"
TARGET_PATH = "/T_GPT/GPT_LOGS/2025/"
OPENAI_API_KEY = os.environ.get("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")

client = OpenAI(api_key=OPENAI_API_KEY)

# ===== 파일 업로드 함수 =====
def upload_to_webdav(file_path, filename):
    with open(file_path, 'rb') as file:
        url = NAS_URL + TARGET_PATH + filename
        response = requests.put(url, data=file, auth=HTTPBasicAuth(USERNAME, PASSWORD), verify=False)
        if response.status_code in [200, 201, 204]:
            print(f"✅ 업로드 성공: {filename}")
        else:
            print(f"❌ 업로드 실패: {response.status_code} - {response.text}")

# ===== 최신 NAS 요약 파일 읽기 =====
def get_latest_summary():
    url = NAS_URL + TARGET_PATH
    response = requests.request("PROPFIND", url, auth=HTTPBasicAuth(USERNAME, PASSWORD), verify=False, headers={"Depth": "1"})
    if response.status_code != 207:
        print("❌ NAS 파일 목록 불러오기 실패")
        return None
    from xml.etree import ElementTree as ET
    tree = ET.fromstring(response.content)
    files = [node.find("{DAV:}href").text for node in tree.findall(".//{DAV:}response") if node.find("{DAV:}href") is not None]
    md_files = [f for f in files if f.endswith(".md")]
    if not md_files:
        return None
    latest = sorted(md_files)[-1]
    download_url = NAS_URL + latest
    content = requests.get(download_url, auth=HTTPBasicAuth(USERNAME, PASSWORD), verify=False).text
    return content

# ===== GPT 응답 함수 (맥락 포함) =====
def chat_with_context(user_input):
    context = get_latest_summary()
    messages = []
    if context:
        messages.append({"role": "system", "content": f"이전 대화 요약:\n{context}"})
    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    return response.choices[0].message.content

# ===== 요약 함수 =====
def summarize_text(text):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "다음 내용을 마크다운 형식으로 간결하게 요약해줘."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content

# ===== 파일 감지 핸들러 =====
class GPTFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(('.txt', '.md')):
            time.sleep(1)  # 파일 안정화 대기
            with open(event.src_path, 'r', encoding='utf-8') as f:
                content = f.read()
            summary = summarize_text(content)
            summary_filename = os.path.splitext(os.path.basename(event.src_path))[0] + "_summary.md"
            summary_path = os.path.join(ICLOUD_PATH, summary_filename)
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            upload_to_webdav(summary_path, summary_filename)

# ===== 메인 실행 =====
def main():
    event_handler = GPTFileHandler()
    observer = Observer()
    observer.schedule(event_handler, ICLOUD_PATH, recursive=False)
    observer.start()
    print("👀 GPTConnect 폴더 감시 중... (종료하려면 Ctrl+C)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
