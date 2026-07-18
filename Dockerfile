# TripWeaver — all-in-one image for a Hugging Face Docker Space.
# Runs the two MCP servers, the FastAPI backend, and the Gradio UI in one
# container; only the Gradio port (7860) is exposed publicly.

FROM python:3.11-slim

# Hugging Face Spaces run containers as a non-root user (uid 1000).
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /home/user/app

# Install dependencies first (better layer caching).
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY --chown=user . .

# Gradio UI (the only public port).
EXPOSE 7860

CMD ["bash", "start.sh"]
