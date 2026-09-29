import feedparser
import json
import os
from google import genai
from google.genai import types

# 從 GitHub Actions 的環境變數讀取金鑰
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
RSS_URL = 'https://nitter.poast.org/aleabitoreddit/rss'
DATA_FILE = 'data.json'

if not GEMINI_API_KEY:
    print("錯誤：找不到 GEMINI_API_KEY 環境變數，請確認 Secrets 是否設定正確。")
    exit(1)

# 初始化 Gemini 客戶端
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# 讀取現有的 JSON 資料庫
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

# 儲存 JSON 資料庫
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 使用 Gemini 分析貼文立場
def analyze_post(post_text):
    prompt = f"""
    你是一位專業的半導體與科技股分析師。請分析以下供應鏈專家的貼文。
    找出推文中提及的上市櫃公司，並判斷作者對該公司的立場。
    
    推文內容："{post_text}"
    
    請輸出 JSON 陣列格式，包含以下欄位：
    - ticker: 股票代號或公司名稱（例如 TSM, NVDA）。若無提及，請回傳空陣列 []。
    - stance: "Bullish", "Bearish", 或 "Neutral"
    - reasoning: 一句話簡述判斷原因
    """
    
    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"AI 分析失敗: {e}")
        return []

def main():
    data = load_data()
    # 建立已處理過的貼文 ID 集合，避免重複分析消耗額度
    processed_ids = {item.get('id') for item in data if 'id' in item}

    print(f"正在讀取 RSS: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)
    
    if not feed.entries:
        print("目前無法抓取到內容（可能是 RSSHub 節點暫時阻擋），請稍後再試。")
        return

    new_updates = False
    
    # 從最舊的開始處理，確保時序正確
    for entry in reversed(feed.entries):
        post_id = entry.get('id', entry.link)
        
        # 如果這篇貼文已經處理過，就跳過
        if post_id in processed_ids:
            continue
            
        print(f"發現新貼文，正在分析: {entry.title[:30]}...")
        post_content = f"{entry.title}\n{entry.get('summary', '')}"
        
        analysis_results = analyze_post(post_content)
        
        for result in analysis_results:
            # 將新資料插入到列表的最前面 (讓網頁呈現時最新的在最上面)
            data.insert(0, {
                'id': post_id,
                'date': entry.published,
                'content': post_content,
                'ticker': result.get('ticker'),
                'stance': result.get('stance'),
                'reasoning': result.get('reasoning')
            })
            new_updates = True

    if new_updates:
        save_data(data)
        print("✅ 資料已更新並存入 data.json")
    else:
        print("沒有新貼文需要更新。")

if __name__ == "__main__":
    main()
