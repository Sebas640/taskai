import { Component, EventEmitter, Output, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TaskService } from '../../services/task';
import { NotificationService } from '../../services/notification';
import { Task } from '../../models/task';

@Component({
  selector: 'app-task-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './task-form.html',
  styleUrl: './task-form.scss'
})
export class TaskFormComponent {
  private taskService = inject(TaskService);
  private notify = inject(NotificationService);
  private cdr = inject(ChangeDetectorRef);

  taskText: string = '';
  isLoading: boolean = false;
  errorMessage: string = '';

  @Output() taskCreated = new EventEmitter<Task>();

  onSubmit(): void {
    if (!this.taskText.trim()) return;

    this.isLoading = true;
    this.errorMessage = '';
    const startTime = performance.now(); // Inicio del cronómetro

    this.taskService.processTask(this.taskText).subscribe({
      next: (newTask) => {
        const endTime = performance.now();
        const duration = ((endTime - startTime) / 1000).toFixed(2);
        this.taskCreated.emit(newTask);
        this.taskText = ''; // Limpia el input tras procesar
        this.isLoading = false;
        this.cdr.markForCheck();

        this.notify.success(`✨ Tarea procesada y guardada en ${duration}s`);
      },
      error: (err) => {
        console.error('Error procesando la tarea:', err);
        // 503 = IA saturada, 429 = cuota agotada: el backend envía un motivo comprensible.
        const motivo = [429, 503].includes(err?.status) && typeof err?.error?.detail === 'string'
          ? err.error.detail
          : null;
        this.errorMessage = motivo ?? 'Ocurrió un error al procesar la tarea con la IA.';
        this.isLoading = false;
        this.cdr.markForCheck();

        this.notify.error(motivo ? `⏳ ${motivo}` : '❌ Error al procesar la tarea con la IA');
      }
    });
  }
}
