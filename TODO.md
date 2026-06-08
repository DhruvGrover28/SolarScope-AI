# TODO - SolarScope fixes

- [x] Implement Render-safe memory behavior (SOLARSCOPE_SAFE_MODE) to prevent OOM during image analysis

- [ ] Reduce image processing cost: cap pixels, downscale uploaded images before segmentation
- [ ] Make GrabCut conditional (disable when safe mode)
- [ ] Tighten HuggingFace detector timeouts/retries (and optionally disable in safe mode)
- [ ] Standardize SECRET_KEY handling for stable session cookies (no random defaults)
- [ ] Add server-side logging for login failures without leaking secrets
- [ ] Update README with required env vars: SECRET_KEY and SOLARSCOPE_SAFE_MODE
- [ ] Run local smoke test: /login + /projects/upload using example3.jpg

