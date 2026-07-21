import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { MetaFunction } from "react-router";
import { z } from "zod";
import { Button } from "~/components/ui/button";
import { Card } from "~/components/ui/card";
import { pageMeta } from "~/lib/seo/metadata";

export const meta: MetaFunction = () =>
  pageMeta({
    title: "Contact Mayabu",
    description:
      "Contact Mayabu about product-data issues, incorrect matches, retailer information, privacy, or general feedback.",
    path: "/contact",
  });

const formSchema = z.object({
  name: z.string().trim().min(2, "Enter your name.").max(80),
  email: z.string().trim().email("Enter a valid email address.").max(160),
  topic: z.string().min(1, "Choose a topic."),
  productUrl: z.string().trim().url("Enter a valid URL.").or(z.literal("")),
  message: z.string().trim().min(20, "Add at least 20 characters.").max(3000),
});
type ContactValues = z.infer<typeof formSchema>;

export default function Contact() {
  const [unavailable, setUnavailable] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ContactValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { name: "", email: "", topic: "", productUrl: "", message: "" },
  });
  const submit = handleSubmit(() => {
    setUnavailable(true);
  });
  const fieldClass =
    "mt-2 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm";
  return (
    <main id="main-content" className="page-container py-12">
      <div className="max-w-3xl">
        <p className="eyebrow">Support and feedback</p>
        <h1 className="mt-2 text-4xl font-black">Contact Mayabu</h1>
        <p className="mt-4 text-lg leading-8 text-slate-600">
          Send feedback, report a product-data problem, or ask about Mayabu. Do not include
          passwords, payment information, or sensitive account details.
        </p>
      </div>
      <Card className="mt-8 max-w-3xl p-6 sm:p-8">
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
          <strong>Support submission is not connected yet.</strong> This form validates the
          information locally, but Mayabu will not claim that a message was recorded until a real
          backend contact endpoint exists.
        </div>
        <form onSubmit={(event) => void submit(event)} noValidate className="grid gap-5">
          <label className="text-sm font-bold">
            Name
            <input {...register("name")} className={fieldClass} autoComplete="name" />
            {errors.name ? (
              <span className="mt-1 block text-xs text-red-700">{errors.name.message}</span>
            ) : null}
          </label>
          <label className="text-sm font-bold">
            Email address
            <input
              {...register("email")}
              type="email"
              className={fieldClass}
              autoComplete="email"
            />
            {errors.email ? (
              <span className="mt-1 block text-xs text-red-700">{errors.email.message}</span>
            ) : null}
          </label>
          <label className="text-sm font-bold">
            Topic
            <select {...register("topic")} className={fieldClass}>
              <option value="">Choose a topic</option>
              <option>Incorrect product match</option>
              <option>Incorrect price or availability</option>
              <option>Missing product</option>
              <option>Retailer or partnership enquiry</option>
              <option>Privacy request</option>
              <option>General feedback</option>
            </select>
            {errors.topic ? (
              <span className="mt-1 block text-xs text-red-700">{errors.topic.message}</span>
            ) : null}
          </label>
          <label className="text-sm font-bold">
            Product URL or Mayabu page{" "}
            <span className="font-normal text-slate-500">(optional)</span>
            <input
              {...register("productUrl")}
              type="url"
              className={fieldClass}
              placeholder="https://"
            />
            {errors.productUrl ? (
              <span className="mt-1 block text-xs text-red-700">{errors.productUrl.message}</span>
            ) : null}
          </label>
          <label className="text-sm font-bold">
            Message
            <textarea {...register("message")} className={`${fieldClass} min-h-40 resize-y`} />
            {errors.message ? (
              <span className="mt-1 block text-xs text-red-700">{errors.message.message}</span>
            ) : null}
          </label>
          <div>
            <Button type="submit" disabled={isSubmitting}>
              Send message
            </Button>
          </div>
          {unavailable ? (
            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4">
              <h2 className="font-black text-red-800">Message could not be sent</h2>
              <p className="mt-1 text-sm text-red-700">
                The Mayabu support endpoint is not available in the current backend. Your message
                was not transmitted or recorded.
              </p>
            </div>
          ) : null}
        </form>
      </Card>
    </main>
  );
}
