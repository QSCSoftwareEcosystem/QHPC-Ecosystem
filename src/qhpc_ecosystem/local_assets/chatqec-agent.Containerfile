# The ChatQEC agent is a service container, never a host subprocess. It
# combines the admitted Tsim tools runtime with the EQO service adapter.
ARG CHATQEC_TSIM_IMAGE=qhpc/chatqec-tsim:dd19a85-linux-amd64

FROM ${CHATQEC_TSIM_IMAGE}

USER root
COPY __init__.py /opt/eqo/qhpc_ecosystem/__init__.py
COPY service_adapters.py /opt/eqo/qhpc_ecosystem/service_adapters.py
COPY chatqec_readiness.py /opt/eqo/qhpc_ecosystem/chatqec_readiness.py
COPY chatqec_agent_service.py /opt/eqo/qhpc_ecosystem/chatqec_agent_service.py
COPY local_assets/chatqec/ /opt/chatqec/
RUN chown -R 65532:65532 /opt/eqo /opt/chatqec

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QHPC_CHATQEC_CONTAINERIZED=1 \
    PYTHONPATH=/opt/eqo:/opt/chatqec-mcp-tools/src

USER 65532:65532
EXPOSE 8096

LABEL org.opencontainers.image.title="EQO ChatQEC contained circuit tools" \
      org.opencontainers.image.description="Pinned ChatQEC Stim and Tsim circuit-tool runtime behind the EQO service contract" \
      org.opencontainers.image.source="https://github.com/QSCSoftwareEcosystem/ChatQEC" \
      org.opencontainers.image.revision="a1ddc2e4916b1f4152fba4c94c9c7512eea0d977" \
      org.opencontainers.image.licenses="MIT AND Apache-2.0" \
      org.qscsoftware.service="chatqec-agent" \
      org.qscsoftware.tool-execution="contained-mcp-only"

ENTRYPOINT ["python", "-m", "qhpc_ecosystem.chatqec_agent_service"]
