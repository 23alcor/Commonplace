---
type: project
status: active
parent: "[[Projects]]"
tags: [project]
---
# Plant Watering Bot

Concepts: [[ESP32]] · [[Soil moisture sensing]] · [[MQTT]]

## Open loops
- [ ] Next milestone TBD

## Log
- 2026-11-12 [[2026-11-12 Plant Watering Bot - Calibrated soil sensor|Calibrated soil sensor]] (coding)


## Update
2026-11-21: System architecture diagram and notes for the ESP32-based Plant Watering Bot.

### System Flow
`soil probe -> ESP32 ADC -> MQTT -> valve`

### Notes
- Capacitive moisture sensor read via ESP32 ADC
- Publish dry/wet status over MQTT
- Threshold triggers relay to open valve

### Next Steps
- [ ] Calibrate dry vs saturated
- [[ESP32]]
- [[MQTT]]
- [[Soil moisture sensing]]
- [[2026-11-12 Plant Watering Bot - Calibrated soil sensor]]
