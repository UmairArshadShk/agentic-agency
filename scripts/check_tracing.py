"""Live check: one real model call through observed_run, then look the trace up in Langfuse.

Needs `make up up-tracing`, `make migrate`, a running Ollama, and the Langfuse keys in .env.
Usage: uv run python scripts/check_tracing.py
"""

import base64
import json
import os
import time
import urllib.request

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from agency.config import load_config
from agency.config.loader import resolve_instances
from agency.db.models import LlmCall, Project
from agency.db.session import make_engine
from agency.llm import get_model
from agency.llm.observe import observed_run

load_dotenv()
cfg = load_config("config/agency.yaml", env=os.environ)
agent = resolve_instances(cfg, "pm")[0]
engine = make_engine()

with Session(engine) as session:
    project = Project(name="tracing-check", owner="owner")
    session.add(project)
    session.commit()
    project_id = project.id

model = get_model(agent, cfg.providers)
with observed_run(
    engine, cfg, agent, project_id=project_id, config_version=1, env=os.environ
) as callbacks:
    model.invoke("Reply with exactly one word: ready", config={"callbacks": callbacks})

with Session(engine) as session:
    row = session.scalars(select(LlmCall).where(LlmCall.project_id == project_id)).one()
print(
    f"llm_calls row: {row.agent} {row.model} in={row.tokens_in} out={row.tokens_out} "
    f"cost={row.cost} config_version={row.config_version} trace_id={row.trace_id}"
)

keys = f"{os.environ['LANGFUSE_PUBLIC_KEY']}:{os.environ['LANGFUSE_SECRET_KEY']}"
auth = base64.b64encode(keys.encode()).decode()
host = os.environ.get("LANGFUSE_HOST", "http://localhost:3000")
url = f"{host}/api/public/v2/observations?traceId={row.trace_id}&limit=10"
for _ in range(12):
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    data = json.load(urllib.request.urlopen(request, timeout=10))["data"]
    if data:
        print("Langfuse observations:", sorted(f"{o['type']}:{o['name']}" for o in data))
        break
    time.sleep(5)
else:
    raise SystemExit("trace did not appear in Langfuse")
