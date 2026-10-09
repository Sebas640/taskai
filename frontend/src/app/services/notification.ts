import { Injectable, signal } from '@angular/core';

export type ToastType = 'success' | 'error';

export interface ToastMessage {
  text: string;
  type: ToastType;
}

/**
 * Estado central de las notificaciones flotantes.
 * Al exponerse como signal, la aplicación zoneless se refresca sola:
 * los componentes ya no necesitan llamar a ChangeDetectorRef.
 */
@Injectable({
  providedIn: 'root'
})
export class NotificationService {
  private static readonly DURATION_MS = 5000;

  private readonly _current = signal<ToastMessage | null>(null);
  readonly current = this._current.asReadonly();

  private timeoutId: ReturnType<typeof setTimeout> | null = null;

  success(text: string): void {
    this.show(text, 'success');
  }

  error(text: string): void {
    this.show(text, 'error');
  }

  show(text: string, type: ToastType = 'success'): void {
    this.clearTimer();
    this._current.set({ text, type });
    this.timeoutId = setTimeout(() => this.dismiss(), NotificationService.DURATION_MS);
  }

  dismiss(): void {
    this.clearTimer();
    this._current.set(null);
  }

  private clearTimer(): void {
    if (this.timeoutId !== null) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
  }
}
