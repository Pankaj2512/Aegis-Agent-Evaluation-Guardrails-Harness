import { redirect } from "next/navigation";

// The workflow list is the home page now (n8n-style). Keep this route as a
// redirect so old links and bookmarks continue to work.
export default function WorkflowsPage() {
  redirect("/");
}
