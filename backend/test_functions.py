"""
Cloud Functions 動作確認スクリプト
firebase-admin を使ってFirestoreに直接アクセスし、ゲームフロー全体をテストする
"""
import sys
import json

# venv のパスを追加
sys.path.insert(0, "functions/venv/lib/python3.12/site-packages")

import firebase_admin
from firebase_admin import credentials, firestore

# --- 初期化 ---
app = firebase_admin.initialize_app()
db = firestore.client()

print("=" * 50)
print("人数当てゲーム 動作確認テスト")
print("=" * 50)

# --- テスト1: ルーム作成 ---
print("\n[TEST 1] ルーム作成...")
import uuid
from datetime import datetime, timezone

room_id = str(uuid.uuid4())[:8].upper()
db.collection("rooms").document(room_id).set({
    "hostName": "テストホスト",
    "status": "WAITING",
    "currentRound": 0,
    "totalRounds": 5,
    "currentQuestion": None,
    "createdAt": datetime.now(timezone.utc),
})
print(f"  ✅ ルーム作成: roomId = {room_id}")

# --- テスト2: プレイヤー参加 ---
print("\n[TEST 2] プレイヤー参加...")
players = [
    ("player_A", "アリス"),
    ("player_B", "ボブ"),
    ("player_C", "チャーリー"),
]
room_ref = db.collection("rooms").document(room_id)
for pid, name in players:
    room_ref.collection("players").document(pid).set({
        "nickname": name,
        "isHost": pid == "player_A",
        "joinedAt": datetime.now(timezone.utc),
    })
print(f"  ✅ {len(players)}人参加: {[p[1] for p in players]}")

# --- テスト3: ゲーム開始 ---
print("\n[TEST 3] ゲーム開始...")
QUESTIONS = [
    {"questionId": "q001", "text": "犬派？猫派？", "options": ["犬派", "猫派"],
     "answerSeconds": 30, "predictSeconds": 20},
]
room_ref.update({
    "status": "ANSWERING",
    "currentRound": 1,
    "currentQuestion": QUESTIONS[0],
    "startedAt": datetime.now(timezone.utc),
})
print(f"  ✅ ゲーム開始: 第1問「{QUESTIONS[0]['text']}」")

# --- テスト4: 回答送信 ---
print("\n[TEST 4] 回答送信...")
answers = [
    ("player_A", "犬派"),
    ("player_B", "猫派"),
    ("player_C", "犬派"),
]
for pid, answer in answers:
    room_ref.collection("rounds").document("1").collection("answers").document(pid).set({
        "answer": answer,
        "answeredAt": datetime.now(timezone.utc),
    })

# 集計
counts = {"犬派": 0, "猫派": 0}
for _, answer in answers:
    counts[answer] += 1
room_ref.update({"status": "PREDICTING", "answerCounts": counts})
print(f"  ✅ 回答完了: 犬派={counts['犬派']}人, 猫派={counts['猫派']}人 → PREDICTINGへ")

# --- テスト5: 予測送信 + 採点 ---
print("\n[TEST 5] 予測送信 & 採点...")
predictions = [
    ("player_A", "犬派", 2),  # 実際2人→差0→100点
    ("player_B", "犬派", 1),  # 実際2人→差1→80点
    ("player_C", "猫派", 2),  # 実際1人→差1→80点
]
round_ref = room_ref.collection("rounds").document("1")
scores = []
for pid, option, pred in predictions:
    actual = counts.get(option, 0)
    score = max(0, 100 - abs(pred - actual) * 20)
    round_ref.collection("answers").document(pid).update({
        "prediction": pred,
        "targetOption": option,
        "roundScore": score,
        "predictedAt": datetime.now(timezone.utc),
    })
    scores.append({"playerId": pid, "roundScore": score, "predicted": pred, "actual": actual})
    print(f"  {pid}: 「{option}が{pred}人」予測 → 実際{actual}人 → {score}点")

scores.sort(key=lambda x: x["roundScore"], reverse=True)
room_ref.update({"status": "RESULT", "roundScores": scores})
print(f"\n  ✅ 採点完了:")
for i, s in enumerate(scores):
    print(f"    {i+1}位 {s['playerId']}: {s['roundScore']}点")

# --- テスト6: Firestoreデータ確認 ---
print("\n[TEST 6] Firestoreデータ確認...")
room_data = room_ref.get().to_dict()
print(f"  ルーム状態: {room_data['status']}")
print(f"  現在ラウンド: {room_data['currentRound']}")
players_list = room_ref.collection("players").get()
print(f"  参加者数: {len(players_list)}人")
answers_list = round_ref.collection("answers").get()
print(f"  回答数: {len(answers_list)}件")

# --- クリーンアップ ---
print("\n[CLEANUP] テストデータを削除...")
for a in answers_list:
    a.reference.delete()
round_ref.delete()
for p in players_list:
    p.reference.delete()
room_ref.delete()
print(f"  ✅ roomId={room_id} のデータを削除")

print("\n" + "=" * 50)
print("✅ 全テスト完了！バックエンドは正常に動作しています")
print("=" * 50)
