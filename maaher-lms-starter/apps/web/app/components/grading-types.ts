export type Score = { criterion_index: number; points: number; comment: string };
export type GradeRevision = { id: string; entry_version: number; revision_no: number; scores: Score[]; total: number; feedback: string; reason: string; reviewer_id: string; created_at: string };
export type Publication = { version: number; state: 'released' | 'withdrawn'; revision_id: string | null; revision_no: number | null; scores: Score[] | null; total: number | null; feedback: string | null; changed_at: string };
export type StudentGrade = { state: 'ungraded' | 'released' | 'withdrawn'; grade: Publication | null };
