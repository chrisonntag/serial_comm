FROM python:3.6

RUN mkdir serial_comm

ENV PYTHONUNBUFFERED 1
ENV APP_ROOT serial_comm

COPY ./requirements.txt /${APP_ROOT}/requirements.txt
RUN pip install -r /${APP_ROOT}/requirements.txt
COPY . /${APP_ROOT}/
WORKDIR /${APP_ROOT}/

RUN touch serial_comm.log
RUN chmod 0777 serial_comm.log

CMD [ "python", "./serial_comm.py" ]
