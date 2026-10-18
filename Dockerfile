
FROM gcc:14-bookworm AS builder

WORKDIR /app
COPY main.c .
RUN gcc -O2 -Wall -o main main.c

FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/main /app/main
COPY server.py index.html style.css script.js ./

ENV PYTHONUNBUFFERED=1

CMD ["python", "server.py"]
