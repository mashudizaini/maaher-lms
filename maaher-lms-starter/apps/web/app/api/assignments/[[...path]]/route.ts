import { NextRequest } from 'next/server';
import { assignmentProxy } from '../../../components/assignment-proxy';
export const dynamic = 'force-dynamic';
export const GET = (request: NextRequest, context: { params: Promise<{path?:string[]}> }) => assignmentProxy('assignments', request, context);
export const POST = GET;
