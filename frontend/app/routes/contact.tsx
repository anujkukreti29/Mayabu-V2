import { HelpCircle, Mail, MessageSquareWarning, Shield } from "lucide-react";
import type { MetaFunction } from "react-router";
import { Link } from "react-router";
import { Reveal } from "~/components/ui/reveal";
import { pageMeta } from "~/lib/seo/metadata";
import { routes } from "~/lib/navigation/routes";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Contact Mayabu",
    description:
      "Contact Mayabu about product-data issues, incorrect matches, retailer information, privacy, or general feedback.",
    path: "/contact",
  });

const TOPICS = [
  {
    icon: MessageSquareWarning,
    title: "Product or price data",
    copy: "Incorrect matches, missing listings, or freshness issues on a product page.",
  },
  {
    icon: Shield,
    title: "Privacy requests",
    copy: "Questions about account data, cookies, or how Mayabu handles personal information.",
  },
  {
    icon: HelpCircle,
    title: "General feedback",
    copy: "Ideas that would make comparison clearer—without inventing features Mayabu cannot support yet.",
  },
] as const;

export default function Contact() {
  return (
    <main id="main-content">
      <section className="border-b border-line marketing-atmosphere">
        <div className="reading-container py-12 sm:py-16">
          <p className="eyebrow">Support</p>
          <h1 className="mt-3 page-title">Contact Mayabu</h1>
          <p className="mt-4 max-w-xl text-body-lg text-ink-muted">
            Reach out about product-data problems, privacy, or feedback. Do not include passwords,
            payment details, or sensitive account credentials.
          </p>
        </div>
      </section>

      <section className="section-space">
        <div className="page-container grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:gap-12">
          <div className="space-y-4">
            {TOPICS.map((topic, i) => {
              const Icon = topic.icon;
              return (
                <Reveal key={topic.title} delayMs={i * 40} className="surface p-5 sm:p-6">
                  <div className="flex gap-4">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-accent-soft text-accent">
                      <Icon className="h-5 w-5" aria-hidden="true" />
                    </span>
                    <div>
                      <h2 className="text-title-sm text-ink">{topic.title}</h2>
                      <p className="mt-1.5 text-sm leading-6 text-ink-muted">{topic.copy}</p>
                    </div>
                  </div>
                </Reveal>
              );
            })}
          </div>

          <Reveal className="surface-elevated h-fit p-6 sm:p-8">
            <Mail className="h-6 w-6 text-accent" aria-hidden="true" />
            <h2 className="mt-4 text-title-sm text-ink">Contact channel status</h2>
            <p className="mt-2 text-sm leading-6 text-ink-muted">
              A live support form and public support inbox are not connected in this release. Until a
              backend contact endpoint and verified mailbox are available, Mayabu will not claim that
              messages can be received through this page.
            </p>
            <p className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-3 text-sm leading-6 text-amber-950">
              For privacy-related requests, see the{" "}
              <Link to={routes.privacy} className="font-semibold underline-offset-2 hover:underline">
                Privacy
              </Link>{" "}
              page for the current policy contact guidance.
            </p>
            <p className="mt-4 text-xs leading-5 text-ink-faint">
              We do not promise 24/7 or one-hour responses.
            </p>
            <div className="mt-6 border-t border-line pt-5 text-sm text-ink-muted">
              Useful links:{" "}
              <Link to={routes.howItWorks} className="font-medium text-accent hover:text-accent-strong">
                How it works
              </Link>
              {" · "}
              <Link to={routes.about} className="font-medium text-accent hover:text-accent-strong">
                About
              </Link>
            </div>
          </Reveal>
        </div>
      </section>
    </main>
  );
}
