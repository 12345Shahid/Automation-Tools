import argparse
import json
from content_engine.engine import create_short_video

def main():
    parser = argparse.ArgumentParser(description="Autonomous Looped-Arc YouTube Shorts Generator ($0 Stack)")
    parser.add_argument("--topic", type=str, default="How AI automates YouTube channels for $0", help="Video topic or viral angle")
    parser.add_argument("--voice", type=str, default="christopher", choices=["christopher", "eric", "jenny", "sonia", "ryan"], help="Voice narrator")
    
    args = parser.parse_args()
    print(f"\n=======================================================")
    print(f"🎬 Starting Autonomous Looped-Arc Content Engine")
    print(f"📌 Topic: {args.topic}")
    print(f"🎙️ Voice: {args.voice}")
    print(f"=======================================================\n")

    res = create_short_video(topic=args.topic, voice_key=args.voice)
    print(f"\n=======================================================")
    print(f"✨ GENERATION COMPLETE!")
    print(f"📁 Video Path: {res['video_path']}")
    print(f"⏱️ Duration: {res['duration']:.2f} seconds")
    print(f"🏷️ Title: {res['title']}")
    print(f"💬 Pinned Comment: {res['pinned_comment']}")
    print(f"🔖 Hashtags: {' '.join(res['hashtags'])}")
    print(f"=======================================================\n")

if __name__ == "__main__":
    main()
