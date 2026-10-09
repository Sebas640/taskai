import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TaskService } from '../../services/task';
import { NotificationService } from '../../services/notification';
import { Task } from '../../models/task';
import { TaskFormComponent } from '../task-form/task-form';
import { AuthService } from '../../services/auth';

@Component({
  selector: 'app-task-list',
  standalone: true,
  imports: [CommonModule, TaskFormComponent],
  templateUrl: './task-list.html',
  styleUrl: './task-list.scss'
})
export class TaskListComponent implements OnInit {
  private authService = inject(AuthService);
  private taskService = inject(TaskService);
  private notify = inject(NotificationService);
  private cdr = inject(ChangeDetectorRef);

  tasks: Task[] = [];
  isLoading: boolean = true;
  errorMessage: string = '';

  ngOnInit(): void {
    this.loadTasks();
  }

  onLogout(): void {
    this.authService.logout();
  }

  // Carga inicial de tareas desde FastAPI
  loadTasks(): void {
    this.isLoading = true;
    this.taskService.getTasks().subscribe({
      next: (data) => {
        this.tasks = data;
        this.isLoading = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error al cargar tareas:', err);
        this.errorMessage = 'No se pudieron cargar las tareas. Asegúrate de que el backend esté corriendo.';
        this.isLoading = false;
        this.cdr.markForCheck();
      }
    });
  }

  // Método público para agregar la nueva tarea creada sin recargar la página
  addTaskToList(newTask: Task): void {
    this.tasks.unshift(newTask); // La agrega al principio de la lista
    this.cdr.markForCheck();
  }

  // Cambiar estado completada/pendiente (PATCH) con actualización en tiempo real
  toggleStatus(task: Task): void {
    const updatedStatus = !task.completed;
    this.taskService.toggleTaskStatus(task.id, updatedStatus).subscribe({
      next: (updatedTask) => {
        // Reasignamos la tarea dentro del arreglo para forzar la reactividad
        const index = this.tasks.findIndex(t => t.id === updatedTask.id);
        if (index !== -1) {
          this.tasks[index] = { ...updatedTask };
        }
        this.cdr.markForCheck();

        this.notify.success(
          updatedTask.completed
            ? '✅ Tarea marcada como completada'
            : '📌 Tarea marcada como pendiente'
        );
      },
      error: (err) => {
        console.error('Error al actualizar estado:', err);
        this.notify.error('❌ Error al cambiar el estado de la tarea');
      }
    });
  }

  // Eliminar tarea (DELETE) con actualización en tiempo real
  deleteTask(id: number): void {
    if (!confirm('¿Estás seguro de que deseas eliminar esta tarea?')) return;

    const startTime = performance.now();

    this.taskService.deleteTask(id).subscribe({
      next: () => {
        const endTime = performance.now();
        const duration = ((endTime - startTime) / 1000).toFixed(2);

        // Filtramos el arreglo (crea una nueva referencia de la lista)
        this.tasks = this.tasks.filter(t => t.id !== id);
        this.cdr.markForCheck();

        this.notify.success(`🗑️ Tarea eliminada correctamente en ${duration}s`);
      },
      error: (err) => {
        console.error('Error al eliminar tarea:', err);
        this.notify.error('❌ Error al eliminar la tarea');
      }
    });
  }
}
