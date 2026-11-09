import Link from "next/link";
import { EmptyState, PageHeader } from "@/components/ui";

export default function NotFound() {
  return (
    <>
      <PageHeader title="Not found" />
      <div className="card">
        <EmptyState title="This page does not exist">
          The link may be mistyped. <Link href="/" className="link">Back to the overview</Link>
        </EmptyState>
      </div>
    </>
  );
}
