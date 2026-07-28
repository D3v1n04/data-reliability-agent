import { ArrowLeft, Compass } from "lucide-react";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <main className="page page--centered">
      <span className="not-found__icon">
        <Compass size={30} />
      </span>
      <span className="eyebrow">404</span>
      <h1>Page not found</h1>
      <p>
        This reliability view does not exist or may have moved.
      </p>
      <Link className="button button--primary" to="/">
        <ArrowLeft size={17} />
        Return to overview
      </Link>
    </main>
  );
}
