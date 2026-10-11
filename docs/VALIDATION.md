# Validation and demonstration

Evidence is recorded in docs/DELIVERY.md after executed checks. Machine-readable measurements live locally under artifacts/ and are never invented. Automated geometry fixtures use synthetic coordinates or blank MP4s and are software tests only. They are not traffic accuracy evidence.

## Manual ground truth

1. Use a short licensed, stationary-camera road video. Record source, hash, resolution, FPS and exact normalized ordered endpoints.
2. Decide the bottom-center box anchor rule and once-per-track/per-direction rule before reviewing footage.
3. Watch the original at reduced speed. Record every visible qualifying crossing in a separate CSV: video_seconds, category, direction. Review ambiguous cases independently. Count vehicles, not model IDs.
4. Run the same complete clip through RoadPulse with those endpoints. Compare events.csv against ground truth within a documented timing tolerance, such as 0.5 video seconds. Pair events by class, direction and appearance; report unmatched events as misses or false positives.
5. Report totals per category and direction, absolute error, misses, false positives, class errors, and ID fragmentation. Do not use count agreement alone as precision/recall evidence. Include occlusions, moving-camera effects and uncertain ground truth.

A preliminary independent visual count was performed on the CC0 reference clip using source-frame contact sheets at 0.5-second intervals, with only the configured line overlaid (no detector boxes or IDs). Seven cars/SUVs visibly crossed from negative to positive side; no motorcycles, buses, trucks or reverse crossings were observed. Approximate independent crossing intervals are in reference-ground-truth.csv. This is a coarse visual audit, not frame-accurate ground truth. The camera tilts/pans, so the line is fixed in image space rather than to a fixed physical road location. A second human review with frame-by-frame playback remains pending. Final algorithm comparison is recorded in DELIVERY.md. A successful pipeline smoke test alone does not prove accuracy.

## Record the first public demo

Use the optional CC0 sample or footage you have rights to share. Start locally, record the empty dashboard, upload the video, place the line, start processing, show genuine progress, then play annotated output and download CSV/JSON. Show actual model/provider and measured throughput. Keep filesystem dialogs, personal paths and unrelated desktop content out of the recording. Inspect exported footage for identifiable details before publication. Credit the sample author and source, even though CC0 does not require attribution.

Inspection of annotated frame 1033 showed the two extra truck events are false detections of roadside traffic-signal equipment during camera movement. The broad line (0.1,0.5) -> (0.9,0.5) intersects that equipment. A second configuration limits the line to the traffic lane: (0.1,0.5) -> (0.45,0.5). Both configurations and their actual outputs are retained locally. This is line placement, not fabricated correction of model events; detector errors remain visible in the annotated output.
