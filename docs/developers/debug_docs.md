# How to setup environment for previewing changes to documentation

<!--* freshness: { owner: 'rechen' reviewed: '2022-06-27' } *-->

The pytype documentation is in markdown format.

github uses [jekyll](https://jekyllrb.com/docs/) to render these pages.

## Prerequisites

Install/update ruby and bundler

```shell
ruby -v # should be greater than 3.0.0
```

If it doesn't exist or is too old

```shell
sudo apt-get install ruby-full
```

Add path to your .bashrc

```shell
echo '# Install Ruby Gems to ~/gems' >> ~/.bashrc
echo 'export GEM_HOME="$HOME/gems"' >> ~/.bashrc
echo 'export PATH="$HOME/gems/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Install packages required for jekyll

```shell
gem install jekyll bundler webrick
gem update jekyll
bundle install
```

## Start jekyll locally

```shell
cd docs # you'll need to be in the pytype/docs directory

bundle exec jekyll serve --watch
```

The `--watch` flag forces jekyll to look for changes to your source files and
reload the server if it detects any changes.

You can view your webpages by navigating to
[http://localhost:4000](http://localhost:4000) like
[http://localhost:4000/developers/index.html](http://localhost:4000/developers/index.html)
