ARG BASE_IMAGE=instinctsam:thor-r39-unified-api-baseline-20260730
FROM ${BASE_IMAGE}

COPY scripts/patch_gi_overlay_fps.py /tmp/patch_gi_overlay_fps.py
COPY scripts/patch_gi_local_trunk.py /tmp/patch_gi_local_trunk.py
RUN python3 /tmp/patch_gi_overlay_fps.py \
      /opt/instinctsam/app/live_tracking_sam3.py \
    && python3 /tmp/patch_gi_local_trunk.py \
      /opt/instinctsam/app/live_tracking_sam3.py \
    && rm /tmp/patch_gi_overlay_fps.py /tmp/patch_gi_local_trunk.py
