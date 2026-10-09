import { Component, inject } from '@angular/core';
import { NotificationService } from '../../../services/notification';

/**
 * Notificación flotante única para toda la aplicación.
 * Se monta una sola vez en app.html; cualquier componente la dispara
 * inyectando NotificationService.
 */
@Component({
  selector: 'app-toast',
  standalone: true,
  templateUrl: './toast.html',
  styleUrl: './toast.scss'
})
export class ToastComponent {
  private readonly notifications = inject(NotificationService);

  readonly toast = this.notifications.current;

  dismiss(): void {
    this.notifications.dismiss();
  }
}
