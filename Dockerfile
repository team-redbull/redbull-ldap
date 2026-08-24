# The image runs under an arbitrary UID on OpenShift (the SCC assigns one),
# so nothing here may depend on a fixed user id -- only on being in group 0.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Group 0 gets whatever the owner has, which is how an arbitrary UID (always
# a member of group 0 on OpenShift) keeps read access to the code.
RUN chgrp -R 0 /app && chmod -R g=u /app

# A non-root default so `runAsNonRoot: true` is satisfied on plain Kubernetes
# too; OpenShift overrides it with a UID from the namespace's range.
USER 1001

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
