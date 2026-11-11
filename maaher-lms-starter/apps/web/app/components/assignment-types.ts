export type Criterion = { criterion: string; max_points: number };
export type ExerciseVersion = { id: string; version_no: number; title: string; instructions: string; language: string; starter_code: string; rubric: Criterion[]; due_at: string | null; max_attempts: number; allow_late: boolean };
export type Submission = { id: string; assignment_id: string; version_id: string; attempt_no: number; draft_revision: number; submitted_at: string; status: string; student_id?: string; source_code?: string; note?: string; assignment_version?: ExerciseVersion };
export const wib = (date: string | null) => date ? new Intl.DateTimeFormat('id-ID', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Jakarta' }).format(new Date(date)) + ' WIB' : 'Tanpa deadline';
