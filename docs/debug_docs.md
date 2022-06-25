---
---

# How to setup environment for previewing changes to documentation

The pytype documentation is in markdown format.

github uses [jekyll](https://jekyllrb.com/docs/) to render these pages.

## Prerequisites

#.  Install/update ruby and bundler

```shell
ruby -v # should be greater than 3.0.0
```

If it doesn't exist or is too old

```shell
sudo apt-get install ruby-full
```

Install packages required for jekyll

```shell
gem install jekyll bundler webrick
gem update jekyll
```

#.  Start jekyll locally

```shell
bundle exec jekyll serve --watch
```

The `--watch` flag forces jekyll to look for changes to your source files and
reload the server if it detects any changes.

You can view your webpages by navigating to http://localhost:4000



