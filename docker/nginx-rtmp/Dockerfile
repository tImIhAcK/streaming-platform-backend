FROM tiangolo/nginx-rtmp:latest

COPY nginx.conf /etc/nginx/nginx.conf

RUN mkdir -p /tmp/hls /tmp/rec && \
    chmod -R 777 /tmp/hls /tmp/rec


EXPOSE 1935 8080 8088
