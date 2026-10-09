import { Injectable, computed, signal } from '@angular/core';

export type FlipDirection = 'open' | 'close';
export type FlipSoundState = 'invite' | 'on' | 'muted';

// Grabación real de una hoja al pasar: "Turn a Page" de CreatorsHome (Pixabay),
// Pixabay Content License — uso libre, sin atribución obligatoria.
// https://pixabay.com/sound-effects/film-special-effects-turn-a-page-336933/
const SOUND_URL = 'sounds/page-turn.mp3';

// --- Parámetros de reproducción (ajustables) ---
const MASTER_VOLUME = 0.5;        // Volumen general (0 - 1); la grabación ya viene normalizada
const START_OFFSET = 0.02;        // Segundos de silencio inicial que se saltan para que suene al instante
const CLOSE_VOLUME = 0.6;         // Volver a girar suena más suave...
const CLOSE_RATE = 0.92;          // ...y algo más grave y lento
const PITCH_JITTER = 0.05;        // Variación aleatoria de velocidad/tono (±5 %)
const PAN_WIDTH = 0.35;           // Recorrido estéreo derecha → izquierda (0 = mono)
const MIN_GAP_MS = 40;            // Separación mínima entre sonidos de la misma dirección

const STORAGE_KEY = 'taskai-flip-sound';

/**
 * Sonido de hoja volteándose para las tarjetas de la landing.
 *
 * Los navegadores no permiten reproducir audio hasta que el usuario hace clic,
 * pulsa una tecla o toca la pantalla: el hover no cuenta. Por eso el audio se
 * desbloquea con el primer gesto válido en cualquier parte del documento, y el
 * estado 'invite' permite a la interfaz pedir ese gesto explícitamente.
 */
@Injectable({
  providedIn: 'root'
})
export class FlipSoundService {
  private readonly enabled = signal(this.readPreference());
  private readonly unlocked = signal(false);

  readonly state = computed<FlipSoundState>(() => {
    if (!this.enabled()) return 'muted';
    return this.unlocked() ? 'on' : 'invite';
  });

  private ctx: AudioContext | null = null;
  private sample: AudioBuffer | null = null;
  private decoding: Promise<void> | null = null;

  // Descargar el archivo no requiere gesto: se adelanta para que esté listo al desbloquear.
  private readonly bytes: Promise<ArrayBuffer | null> = fetch(SOUND_URL)
    .then(response => (response.ok ? response.arrayBuffer() : null))
    .catch(() => null);

  // Por dirección: al pasar de una tarjeta a otra, el 'close' de la anterior y el
  // 'open' de la nueva llegan casi a la vez y ninguno debe anular al otro.
  private readonly lastPlayedAt: Record<FlipDirection, number> = { open: 0, close: 0 };

  private readonly onGesture = (event: Event) => {
    // El botón de sonido gestiona su propio desbloqueo en toggle(); si también
    // lo hiciera este listener, el clic de "Activar sonido" lo silenciaría.
    if ((event.target as Element | null)?.closest?.('[data-sound-toggle]')) return;
    this.unlock();
  };

  constructor() {
    // Si el usuario ya interactuó con la página (p. ej. volvió desde /login),
    // el navegador ya permite sonar y no hace falta esperar otro gesto.
    if ((navigator as Navigator & { userActivation?: { hasBeenActive: boolean } })
      .userActivation?.hasBeenActive) {
      this.unlock();
    } else {
      this.listenForGesture(true);
    }
  }

  play(direction: FlipDirection = 'open'): void {
    if (!this.enabled() || !this.unlocked() || !this.ctx || !this.sample) return;

    const now = performance.now();
    if (now - this.lastPlayedAt[direction] < MIN_GAP_MS) return;
    this.lastPlayedAt[direction] = now;

    const jitter = 1 + (Math.random() * 2 - 1) * PITCH_JITTER;
    this.schedule(this.ctx, this.sample, direction, this.ctx.currentTime, jitter);
  }

  /** Acción del botón 🔊/🔇. Debe llamarse desde un clic (gesto del usuario). */
  async toggle(): Promise<void> {
    if (this.state() === 'invite') {
      await this.unlock();
      this.play('open'); // Confirmación audible de que el sonido funciona.
      return;
    }

    const next = !this.enabled();
    this.enabled.set(next);
    this.writePreference(next);

    if (next) {
      await this.unlock();
      this.play('open');
    }
  }

  /**
   * Programa la grabación en cualquier contexto de audio (también en un
   * OfflineAudioContext, lo que permite renderizarla y medirla sin altavoces).
   */
  private schedule(
    ctx: BaseAudioContext,
    sample: AudioBuffer,
    direction: FlipDirection,
    t: number,
    rate: number
  ): void {
    const closing = direction === 'close';
    const playbackRate = rate * (closing ? CLOSE_RATE : 1);
    const duration = (sample.duration - START_OFFSET) / playbackRate;

    // Estéreo: la hoja viaja de derecha a izquierda (al revés al volver).
    let output: AudioNode = ctx.destination;
    if (typeof ctx.createStereoPanner === 'function' && PAN_WIDTH > 0) {
      const panner = ctx.createStereoPanner();
      const from = closing ? -PAN_WIDTH : PAN_WIDTH;
      panner.pan.setValueAtTime(from, t);
      panner.pan.linearRampToValueAtTime(-from, t + duration);
      panner.connect(ctx.destination);
      output = panner;
    }

    const gain = ctx.createGain();
    gain.gain.value = MASTER_VOLUME * (closing ? CLOSE_VOLUME : 1);

    const source = ctx.createBufferSource();
    source.buffer = sample;
    source.playbackRate.value = playbackRate;
    source.connect(gain).connect(output);
    source.start(t, START_OFFSET);
  }

  private async unlock(): Promise<void> {
    try {
      if (!this.ctx) {
        this.ctx = new AudioContext();
        this.ctx.onstatechange = () => this.unlocked.set(this.ctx?.state === 'running');
      }
      if (this.ctx.state === 'suspended') {
        await this.ctx.resume();
      }
      await this.decodeSample(this.ctx);
      this.unlocked.set(this.ctx.state === 'running');
    } catch {
      this.unlocked.set(false);
    }

    if (this.unlocked()) {
      this.listenForGesture(false);
    }
  }

  /** Decodifica una sola vez: decodeAudioData consume el ArrayBuffer. */
  private decodeSample(ctx: AudioContext): Promise<void> {
    this.decoding ??= this.bytes.then(async data => {
      if (!data) {
        console.warn(`FlipSoundService: no se pudo cargar ${SOUND_URL}`);
        return;
      }
      this.sample = await ctx.decodeAudioData(data);
    });
    return this.decoding;
  }

  private listenForGesture(active: boolean): void {
    const events = ['pointerdown', 'keydown', 'touchend'];
    for (const type of events) {
      if (active) {
        document.addEventListener(type, this.onGesture, { capture: true });
      } else {
        document.removeEventListener(type, this.onGesture, { capture: true });
      }
    }
  }

  private readPreference(): boolean {
    try {
      return localStorage.getItem(STORAGE_KEY) !== 'off';
    } catch {
      return true;
    }
  }

  private writePreference(enabled: boolean): void {
    try {
      localStorage.setItem(STORAGE_KEY, enabled ? 'on' : 'off');
    } catch {
      // Almacenamiento no disponible (modo privado): la preferencia dura solo esta visita.
    }
  }
}
