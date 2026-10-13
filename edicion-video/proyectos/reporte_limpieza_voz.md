# Limpieza de voz: reel TGH «3 errores»

## Entregables
- `Voz_limpia.wav`: 48 kHz, 24 bit, estéreo L=R, 1.148.928 muestras (23,936 s), las mismas que el audio decodificado del video. Arranca en 0 y está en sincronía (desfase 0 muestras).
- `Voz_cruda.wav`: referencia para el A/B.
- `espectro_antes.png` y `espectro_despues.png`: misma escala (dBFS absolutos, 100 dB de rango).
- Script: `/home/user/nube-calude/edicion-video/proyectos/limpiar_voz.py`. Uso: `python3 limpiar_voz.py entrada salida.wav [--preset natural|intenso] [--mono] [--lufs -16] [--tp -1.5] [--sin-ia]`.

**Para el editor:** pon el WAV en el frame 0 y silencia el audio original del clip. La voz sola va a -16 LUFS. Para la mezcla final con música y efectos, conviene apuntar a -14 LUFS y -1,5 dBTP. El WAV dura 2,7 ms más que la pista de video por el relleno del AAC; no afecta.

## Diagnóstico del crudo
| Medida | Valor | Lectura |
|---|---|---|
| Sonoridad / true peak / LRA | -8,5 LUFS / 0,0 dBTP / 1,2 LU | Ya llegó masterizado y limitado al extremo |
| Factor de cresta | 12 dB | Bajo, propio de un audio limitado |
| Clipping | Recorte duro en 0,825 (-1,7 dBFS): acumulación 2,9× en el histograma, 4.821 muestras (0,42 %), rachas de hasta 20 muestras; el AAC luego llega a 0 dBFS | Distorsión en sílabas fuertes |
| Piso en pausas | -32 a -44 dB bajo la voz (-43,5 dBFS) | Ruido de sala moderado |
| Percentil 10 de RMS en 50 ms | -24,8 dBFS (-13 dB bajo la voz) | Son huecos entre sílabas, no ruido |
| silencedetect | Una sola pausa (16,92-17,09 s); 8 cortes de video, todos limpios | Sin clics de edición |
| Bandas (dB respecto al total) | sub -37,4 · 80-250 -13,3 · barro -6,3 · 500-2k -2,7 · presencia -8,1 · sibilancia -18,1 · aire -24,1 | Meseta de 200-800 Hz, poca presencia y aire (solapa en el pecho) |
| Zumbido 50/60 Hz | Picos de 3,4 dB o menos sobre la vecindad | No hay |
| Reverberación (RT60 aprox.) | 0,39 s | Leve; la desreverberación WPE no cambió nada |
| Transitorios de alta frecuencia | 101 (53 fuertes) | Chasquidos de boca y plosivas |

## Cadena `natural`
1. Declipping por consistencia y dispersión STFT (60 iteraciones, techo 1,6×). En prueba sintética el SDR sube de 17,2 a 27,5 dB y de 13,1 a 21,1 dB.
2. Paso alto de 80 Hz, fase cero, 24 dB/oct.
3. Barro: -2,5 dB en 320 Hz, Q 1.
4. Compresor 3:1 (ataque 8 ms, release 100 ms) adaptativo por LRA. Con LRA menor de 4 LU solo controla picos (umbral +4 dB sobre la voz; reducción mediana 0 dB, p95 1 dB).
5. Presencia +2,5 dB en 4 kHz y aire +2 dB con shelf en 11 kHz.
6. DeepFilterNet3 usado como máscara real sobre el original, con STFT de 21 ms y 24 bandas. En cada banda con voz (6-14 dB sobre su piso) atenúa como máximo 6 dB; en pausas, sin límite.
7. De-esser en 5,5-9 kHz con división de fase cero: 4:1 sobre el percentil 85, máximo 6 dB.
8. Expansor 1:2: umbral 18 dB bajo la voz, rango 10 dB, look-ahead 10 ms, hold 40 ms, cierre 30 ms, apertura 3 ms.
9. Normalización a -16 LUFS medidos sobre el archivo estéreo entregado, con limitador true-peak ×4.

## Configuraciones probadas
Criterio, por orden: el WER no puede empeorar, cero huecos, el ruido de sala baja al menos 12 dB, mejor DNSMOS y sibilancia controlada.

| # | Cadena | Resultado | Decisión |
|---|---|---|---|
| 1 | DFN a24 → compresor con 4,5 dB de reducción → expansor lento | OVRL 2,21; SNR -1,8 dB; WER 9,2 % | Descartada |
| 2 | DFN a30 sin protección | OVRL 2,62; WER 18,5 %; 1,9 s de huecos de más de 10 dB | Descartada |
| 3 | DFN sin límite | OVRL 2,69; WER 23,1 % | Descartada |
| 4 | Protección de banda ancha 6 dB | WER 3,1 %; OVRL 2,30; 141 ms de huecos de -40 dB en graves | Descartada |
| **5** | **Protección por bandas 6 dB (`natural`)** | **WER 4,6 %; DNSMOS 3,46 / 2,34 / 2,36; 0 huecos** | **Elegida** |
| 6 | `intenso` (protección 9 dB, más EQ, expansor 14 dB) | WER 3,1 %; DNSMOS 3,42 / 2,19 / 2,27; sibilancia p99 -2,7 | Alternativa (`--preset intenso`) |

Comparación de reductores sobre la misma entrada:
- WER con Whisper int8: DFN con límite 6/12/18/30 dB → 3,1 / 7,7 / 10,8 / 20 %; noisereduce → 4,6 %; RNNoise cb (mix 0,6) → 6,2 %.
- DNSMOS global: DFN a30 2,57; noisereduce 2,25; RNNoise 2,00-2,27.

## Métricas antes y después
| Métrica | Crudo | Limpia | intenso |
|---|---|---|---|
| Muestras / desfase | 1.148.928 | 1.148.928 / 0 (local ≤ 1 muestra por la fase de la EQ) | igual |
| LUFS / true peak / LRA | -8,5 / 0,0 / 1,2 | -16,0 / -3,0 / 1,8 | -16,0 / -1,9 / 2,0 |
| Clipping | 4.821 muestras recortadas | 0 | 0 |
| Ruido de sala, 6 ventanas (dB bajo la voz) | -32,0 · -40,5 · -41,6 · -35,2 · -38,2 · -44,0 | -44,7 · -54,7 · -57,8 · -49,4 · -54,8 · -61,5 | -48,4 · -58,3 · -61,5 · -50,9 · -58,1 · -65,2 |
| Mejora del ruido de sala | — | 12,7 a 17,5 dB (mediana 15,2) | 16,4 a 21,2 dB |
| SNR voz / ruido de sala | 39,4 dB | 54,8 dB | 58,2 dB |
| SNR frente a todas las pausas (incluye colas de palabra) | 25,0 dB | 26,9 dB | 26,3 dB |
| Ventana 11,65 s (cola sonora; 300-3000 Hz, planitud 0,09) | -24,5 | -30,8 | -33,9 |
| Percentil 10 de RMS | -13,0 | -13,4 | -13,1 |
| Bandas | -37,4 · -13,3 · -6,3 · -2,7 · -8,1 · -18,1 · -24,1 | -51,1 · -13,7 · -7,5 · -3,1 · -5,8 · -18,7 · -20,3 | -51,4 · -13,6 · -7,8 · -3,5 · -5,2 · -18,5 · -18,9 |
| Sibilancia media / p99 | -17,3 / -3,4 | -17,7 / -4,3 | -17,4 / -2,7 |
| Transitorios HF (total / fuertes) | 101 / 53 | 76 / 15 | 72 / 15 |
| Huecos (ms) | — | 0 / 0 | 0 / 0 |
| DNSMOS SIG / BAK / OVRL | 3,33 / 1,96 / 2,10 | 3,46 / 2,34 / 2,36 | 3,42 / 2,19 / 2,27 |
| WER Whisper small (fp32) | 4,6 % | 4,6 % | 3,1 % |

El piso absoluto pasa de -43,5 a -59,6 dBFS, pero incluye los 7,5 dB de la normalización; la mejora real es la relativa a la voz.

## Inteligibilidad (Whisper small fp32, es)
- **Crudo:** falla "pocos", "ley" (por "lectura") y "Comentes".
- **Limpia:** falla "pocos", "ley" y "estos 13" (por "tres"); acierta "Cometes".

"Pocos" y "ley" fallan en las dos versiones: es habla rápida, no un problema de audio. "Estos 13" parece variación de Whisper: en la pasada int8 salió "tres" bien y no hay huecos medidos en esa zona.

## Espectrogramas
- **Antes:** niebla de ruido entre armónicos hasta unos 16 kHz y muchos clics de banda ancha hasta 22 kHz.
- **Después:** armónicos intactos (incluidos "Tres errores" y "Error 1"), pausas negras, sin ruido musical, sin huecos y sin bandas cortadas, con menos clics.

## Herramientas
- **DeepFilterNet** `deep-filter` 0.5.6 musl en `/root/.cache/limpiar_voz/bin/deep-filter`, sha256 `70775e251eee44c0f2451a1e833326cf8bcbbe304d3e7cd12851e6fce72ef7da`. El script lo descarga y verifica si falta, y también localiza los binarios de macOS y Windows.
- **pip:** soundfile y pyloudnorm (los usa el script); noisereduce (respaldo); onnxruntime y nara_wpe (solo para pruebas).
- **Solo para pruebas (en el scratchpad):** modelos RNNoise en `dl_rnn/`, DNSMOS en `dl_dnsmos/`, Silero VAD v5 en `dl_vad/`. El VAD se descartó porque no detecta bien el "Tres errores" inicial.
- **Verificación:** `scratchpad/audio_work/{metricas.py, dnsmos.py, whisper_wer.py, evaluar.py}` y los resultados en `evaluacion.json`.