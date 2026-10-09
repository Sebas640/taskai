import { Routes } from '@angular/router';
import { LandingComponent } from './components/landing/landing';
import { LoginComponent } from './components/auth/login';
import { RegisterComponent } from './components/auth/register';
import { TaskListComponent } from './components/task-list/task-list';
import { authGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', component: LandingComponent }, // Carga la Landing Page como página de inicio
  { path: 'login', component: LoginComponent },
  { path: 'register', component: RegisterComponent },
  {
    path: 'tasks',
    component: TaskListComponent,
    canActivate: [authGuard]
  },
  { path: '**', redirectTo: '' } // Cualquier ruta no encontrada redirige a la Landing
];
