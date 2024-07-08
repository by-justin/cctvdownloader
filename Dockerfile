FROM python:latest

VOLUME /data

RUN \
  git clone  https://github.com/yt-dlp/yt-dlp.git /app &&\
  cd /app &&\
  git checkout 39bc699d2e6e39

COPY ./requirements.txt /app

RUN \ 
  pip3 install -r /app/requirements.txt 

COPY ./main.py /app
COPY ./cctv.html /app
COPY cctv_patched.py /app/yt_dlp/extractor/cctv.py

CMD python3 /app/main.py
