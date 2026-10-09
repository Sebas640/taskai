export interface Task {
  id: number;
  title: string;
  due_date: string | null;
  category: string;
  priority: string;
  completed: boolean;
  ai_analysis?: string;
}

export interface TaskCreateRequest {
  text: string;
}

export interface TaskUpdateRequest {
  title?: string;
  due_date?: string | null;
  category?: string;
  priority?: string;
  completed?: boolean;
}
