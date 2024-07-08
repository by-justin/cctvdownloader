import argparse
import json
import logging
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests


def setup_logging(debug=False):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler("app.log"),
            logging.StreamHandler(),
        ],
    )


def request_html(link):
    try:
        response = requests.get(link)
        response.raise_for_status()  # Check for HTTP errors
        response.encoding = "utf-8"  # Ensure the encoding is set to utf-8
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(
            f"Can't get the requested link, status code {
                response.status_code if 'response' in locals() else 'N/A'}"
        )
        logging.error(e)
        exit(1)


def get_program_title(program_link):
    html = request_html(program_link)
    pattern = r"<title>(.*)</title>"
    match = re.search(pattern, html)
    if not match:
        logging.warning("Can't locate program title.")
        return ""
    return match.group(1)


def get_topc(program_link):
    html = request_html(program_link)
    pattern = r".*(TOPC[0-9]+).*"
    match = re.search(pattern, html)
    if not match:
        logging.error("Can't locate program id.")
        exit(1)
    return match.group(1)


def get_video_list(topc, limit=0):
    def request_url_f(topc, page):
        return (
            f"https://api.cntv.cn/NewVideo/getVideoListByColumn?id={topc}"
            f"&n=100&sort=desc&p={
                page}&d=&mode=0&serviceId=tvcctv&callback=lanmu_0"
        )

    def jsonify(response_text):
        return json.loads(response_text.lstrip("lanmu_0(").rstrip(");"))

    def parse(entry):
        return (entry["url"], entry["title"], entry["time"])

    result_list = []
    for pg in range(0, 1000):
        response = requests.get(request_url_f(topc, pg))
        response_json = jsonify(response.text)
        video_list = response_json["data"]["list"]
        result_list += video_list
        logging.info(f"Fetched {len(video_list)} video info from page {pg}")
        if not video_list or (limit and len(result_list) > limit):
            break

    if limit:
        result_list = result_list[:limit]

    return [parse(e) for e in result_list]


def check_resolution(link, yt_dlp_dir):
    download_command = ["python3", str(Path(yt_dlp_dir) / "__main__.py"), "-F", link]

    result = subprocess.run(
        download_command, check=True, capture_output=True, text=True
    )

    res_tiers = []
    for i in range(100):
        if f"hls-{i}" not in result.stdout:
            break
        res_tiers.append(f"hls-{i}")

    return res_tiers


def check_program(yt_dlp_dir):
    TEST_LINK = "https://tv.cctv.com/2024/06/14/VIDEAO2aMkgnG6AouAOuSKs1240614.shtml"
    res = check_resolution(TEST_LINK, yt_dlp_dir)
    if len(res) != 4:
        logging.error("yt-dlp is not configured correctly")
        exit(-1)


def safe_title_f(video_title):
    return "".join(c if c.isalnum() else "_" for c in video_title)


def output_path_f(output_path_str, video_title, res, date):
    output_path = Path(output_path_str)
    safe_title = safe_title_f(video_title)
    return str(output_path / f"{date}_{safe_title}_{res}.mp4")


def do_video_exist(output_path_str, video_title):
    safe_video_title = safe_title_f(video_title)
    for filename in os.listdir(output_path_str):
        if safe_video_title in filename and filename.endswith(".mp4"):
            return True
    return False


def download_video(
    video_info, output_dir, index, total_videos, fragment_thread, yt_dlp_dir
):
    link, title, date = video_info
    if do_video_exist(output_dir, title):
        logging.info(f"Video {title} exists, skipping.")
        return

    res = check_resolution(link, yt_dlp_dir)[-1]
    output_path = output_path_f(output_dir, title, res, safe_title_f(date))
    download_command = [
        "python3",
        str(Path(yt_dlp_dir) / "__main__.py"),
        "-f",
        res,
        link,
        "-N",
        str(fragment_thread),
        "-o",
        str(output_path),
    ]
    logging.info(f"Start downloading {title}")
    logging.debug(" ".join(download_command))

    try:
        subprocess.run(
            download_command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        logging.error(
            f"Command '{e.cmd}' returned non-zero exit status {e.returncode}."
        )
        os._exit(e.returncode)

    while not Path(output_path).exists():
        time.sleep(1)

    logging.info(f"Downloaded complete {index + 1} / {total_videos}: {title}")


def main():
    parser = argparse.ArgumentParser(
        description="CCTV program scraper, written by-justin.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("program_url", type=str, help="URL of the program")
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=0,
        help="Limit for the number of videos to download (0 for no limit)",
    )
    parser.add_argument(
        "-d",
        "--output_dir",
        type=str,
        default="/data/videos",
        help="Directory to save downloaded videos",
    )
    parser.add_argument(
        "-j",
        "--download_thread",
        type=int,
        default=4,
        help="Number of download threads",
    )
    parser.add_argument(
        "-N",
        "--fragment_thread",
        type=int,
        default=8,
        help="Number of fragment threads",
    )
    parser.add_argument(
        "-D",
        "--yt_dlp_dir",
        type=str,
        default="/app/yt_dlp",
        help="Directory of patched yt-dlp repo that contains __main__.py",
    )
    parser.add_argument(
        "--skip_check",
        type=bool,
        default=False,
        help="Skip checking if yt-dlp is patched",
    )
    parser.add_argument(
        "--debug",
        type=bool,
        default=False,
        help="Enable debug logging",
    )
    args = parser.parse_args()

    program_url = args.program_url
    limit = args.limit
    output_dir = args.output_dir
    download_thread = args.download_thread
    fragment_thread = args.fragment_thread
    yt_dlp_dir = args.yt_dlp_dir
    skip_check = args.skip_check
    debug = args.debug

    setup_logging(debug)

    if not skip_check:
        logging.info("Checking if yt_dlp patched...")
        check_program(yt_dlp_dir)
        logging.info("Checks passed.")

    topc = get_topc(program_url)
    program_title = get_program_title(program_url)
    logging.info(f"Downloading video list for program {program_title}")
    logging.debug(f"Program TOPC: {topc}")
    video_list = get_video_list(topc, limit)
    logging.info(
        f"Found {len(video_list)} videos, start downloading with {
            download_thread} threads after 3 seconds"
    )
    time.sleep(3)

    Path(output_dir).mkdir(exist_ok=True)
    total_videos = len(video_list)

    with ThreadPoolExecutor(max_workers=download_thread) as executor:
        future_to_video = {
            executor.submit(
                download_video,
                video_info,
                output_dir,
                index,
                total_videos,
                fragment_thread,
                yt_dlp_dir,
            ): video_info
            for index, video_info in enumerate(video_list)
        }

        for future in as_completed(future_to_video):
            video_info = future_to_video[future]
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error downloading video {video_info[1]}: {e}")


if __name__ == "__main__":
    main()
