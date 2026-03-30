# Instagram Setup

This checklist covers the remaining setup required before ShirtClawd can publish live to Instagram.

## Recommended API Path

Use the Instagram API with Instagram Login.

This is the better fit for ShirtClawd because:

- it supports Instagram professional accounts
- it supports creators and businesses
- it supports content publishing
- it does not require a Facebook Page link in the current Meta setup

If your Instagram account is already linked to a Facebook Page, that is fine, but it is not the main blocker anymore.

## What You Need

Before live publishing will work, you need:

1. A professional Instagram account
2. A Meta developer app
3. Instagram API product enabled on that app
4. Login configured for the app
5. An access token with Instagram publishing scope
6. The Instagram account added as a tester or otherwise authorized during development

## Suggested Env Vars

Plan to store these in `.env`:

```env
INSTAGRAM_ACCESS_TOKEN=replace_me
INSTAGRAM_BUSINESS_ACCOUNT_ID=replace_me
```

Depending on the final Meta app setup, we may also want:

```env
INSTAGRAM_APP_ID=replace_me
INSTAGRAM_APP_SECRET=replace_me
```

## Setup Steps

1. Log in to Meta for Developers with the Facebook login that owns or manages the Instagram account.
2. Create a new app.
3. Choose a business-oriented app type if Meta asks.
4. Add the Instagram API product.
5. Configure Instagram Login for the app.
6. Add the Instagram account as an app tester or authorized user if Meta requires that in development mode.
7. Generate a user access token with Instagram publishing permission.
8. Identify the Instagram account ID that Meta expects for publishing calls.
9. Put the token and account ID into `.env`.
10. Test a dry-run publisher first, then a real image post.

## Permissions To Look For

The current Meta naming uses Instagram business scope names.

The important one for publishing is:

- `instagram_business_content_publish`

You will likely also need the basic read scope:

- `instagram_business_basic`

## Implemented In Repo

The repo now includes:

1. `bot/instagram_publisher.py`
2. `publish_to_instagram.py`
3. Tests for dry-run behavior and caption handling

Current scope is:

- single-image feed posts only
- dry-run and live CLI support
- no approval queue yet

The main remaining blocker is valid Meta auth.

## Notes

- Do not use a personal-only Instagram account.
- Creator is okay.
- Business is okay.
- Stories have different limitations than feed posts, so v1 targets feed posts only.

## Sources

Official Meta references used for this checklist:

- [Instagram API documentation on Postman](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
- [Instagram API with Instagram Login on Postman](https://www.postman.com/meta/workspace/instagram/documentation/23987686-9386f468-7714-490f-9bfc-9442db5c8f00)
- [Instagram APIs product page](https://developers.facebook.com/products/instagram/apis/)
