FROM python:3.6

ENV PYTHONUNBUFFERED 1

RUN mkdir serial_evcs

COPY ./requirements.txt /serial_evcs/requirements.txt
RUN pip install -r /serial_evcs/requirements.txt
COPY . /serial_evcs/
WORKDIR /serial_evcs/

RUN touch serial_comm.log
RUN chmod 0777 serial_comm.log

CMD [ "python", "./serial_comm.py" ]
