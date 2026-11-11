import { Criterion, wib } from './assignment-types';
import { StudentGrade } from './grading-types';
export default function PublishedGrade({ value, rubric }: { value: StudentGrade | null; rubric: Criterion[] }) {
  const grade = value?.grade;
  return <section aria-label="Nilai submission" className="grade-result"><h4>Nilai &amp; feedback</h4>
    {value?.state === 'released' && grade ? <><p className="grade-total">Nilai {grade.total}/100</p><p>Revisi nilai {grade.revision_no} · Dibagikan {wib(grade.changed_at)}</p>
      <ul>{grade.scores?.map(score => <li key={score.criterion_index}><strong>{rubric[score.criterion_index]?.criterion}</strong>: {score.points}/{rubric[score.criterion_index]?.max_points}<p className="feedback-text">{score.comment}</p></li>)}</ul>
      <h5>Feedback pengajar</h5><p className="feedback-text">{grade.feedback || 'Tidak ada catatan tambahan.'}</p></>
      : <p>{value?.state === 'withdrawn' ? 'Nilai ditarik untuk ditinjau ulang oleh pengajar.' : 'Nilai belum dibagikan oleh pengajar.'}</p>}
  </section>;
}
