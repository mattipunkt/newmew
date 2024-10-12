FROM python:alpine

WORKDIR /data
COPY . /data/

RUN python -m pip install -r /data/requirements.txt

RUN chmod +x /data/entrypoint.sh

ENTRYPOINT [ "/data/entrypoint.sh" ]