"""
Masked-hint generation for the candidate claim challenge.

The hint is shown publicly on the claim screen, so it is deliberately
aggressive: enough for a real candidate to recognise which of their addresses
was filed with the clerk, not enough for a stranger to reconstruct it.

    jane@guelphward4.ca      ->  j•••@g•••.ca
    j.doe@guelph.on.ca       ->  j•••@g•••.on.ca
    a@x.com                  ->  a•••@x•••.com

Never raises. Clerk-sourced data contains malformed addresses, and an
exception here means a 500 on a candidate's own claim screen — i.e. a
candidate who never claims. Unusable input returns None, which the endpoint
renders as the no-email-on-file holding screen, routing the candidate to the
contact form so an operator can fix the row.
"""

BULLETS = "\u2022\u2022\u2022"  # fixed length, never varies with input


def normalize_email(raw):
    """
    Canonical form for both storage comparison and masking.

    Deliberately minimal: strip, lowercase, drop a stray 'mailto:' prefix.
    No Gmail dot-stripping, no plus-tag removal — on-file addresses are mostly
    custom campaign domains where those rules don't apply and would create
    false matches.

    Returns None if the result isn't usable as an address.
    """
    if not raw or not isinstance(raw, str):
        return None

    value = raw.strip().lower()

    if value.startswith("mailto:"):
        value = value[7:].strip()

    # Strip surrounding angle brackets: "<jane@example.ca>"
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1].strip()

    if value.count("@") != 1:
        return None

    local, _, domain = value.partition("@")

    if not local or not domain:
        return None
    if "." not in domain:
        return None
    if domain.startswith(".") or domain.endswith("."):
        return None
    if any(not label for label in domain.split(".")):
        return None
    if any(c.isspace() for c in value):
        return None

    return value


def mask_email(raw):
    """
    Build the public hint. Returns None for unusable input.

    Masks the local part and the first domain label only; remaining labels are
    preserved so multi-part suffixes survive (.on.ca, .co.uk).

    Tradeoff worth knowing: for a three-label domain like mail.example.com this
    yields m•••.example.com, which reveals more than the two-label case. Rare
    in nomination filings — clerk-listed campaign addresses are almost always
    <name>@<campaign-domain>.<tld> or a consumer mailbox.
    """
    value = normalize_email(raw)
    if value is None:
        return None

    local, _, domain = value.partition("@")
    labels = domain.split(".")

    masked_local = local[0] + BULLETS
    masked_domain = ".".join([labels[0][0] + BULLETS] + labels[1:])

    return masked_local + "@" + masked_domain


def addresses_match(typed, on_file):
    """
    Constant-time comparison of the typed challenge answer against the on-file
    address. Both are normalized first.

    The typed value is compared and discarded — never stored, never a delivery
    destination.
    """
    import hmac

    a = normalize_email(typed)
    b = normalize_email(on_file)

    if a is None or b is None:
        return False

    return hmac.compare_digest(a, b)


if __name__ == "__main__":
    cases = [
        # (input, expected mask)
        ("jane@guelphward4.ca",        "j\u2022\u2022\u2022@g\u2022\u2022\u2022.ca"),
        ("j.doe@guelph.on.ca",         "j\u2022\u2022\u2022@g\u2022\u2022\u2022.on.ca"),
        ("a@x.com",                    "a\u2022\u2022\u2022@x\u2022\u2022\u2022.com"),
        ("  Jane@Example.CA  ",        "j\u2022\u2022\u2022@e\u2022\u2022\u2022.ca"),
        ("mailto:jane@example.ca",     "j\u2022\u2022\u2022@e\u2022\u2022\u2022.ca"),
        ("<jane@example.ca>",          "j\u2022\u2022\u2022@e\u2022\u2022\u2022.ca"),
        ("jane+ward4@example.co.uk",   "j\u2022\u2022\u2022@e\u2022\u2022\u2022.co.uk"),
        # Unusable — must return None, must not raise
        ("",                           None),
        (None,                         None),
        ("   ",                        None),
        ("notanemail",                 None),
        ("jane@",                      None),
        ("@example.ca",                None),
        ("jane@@example.ca",           None),
        ("jane@example",               None),
        ("jane@.ca",                   None),
        ("jane@example..ca",           None),
        ("jane doe@example.ca",        None),
        (12345,                        None),
    ]

    failures = 0
    for raw, expected in cases:
        try:
            got = mask_email(raw)
        except Exception as exc:
            print("RAISED  {!r}: {}".format(raw, exc))
            failures += 1
            continue
        status = "ok  " if got == expected else "FAIL"
        if got != expected:
            failures += 1
        print("{} {!r:32} -> {!r}".format(status, raw, got))

    print()
    print("match  jane@example.ca vs JANE@EXAMPLE.CA :",
          addresses_match("jane@example.ca", "JANE@EXAMPLE.CA"))
    print("match  jane@example.ca vs jan@example.ca  :",
          addresses_match("jane@example.ca", "jan@example.ca"))
    print("match  malformed vs anything             :",
          addresses_match("notanemail", "jane@example.ca"))

    print()
    print("FAILURES: {}".format(failures) if failures else "all cases passed")
