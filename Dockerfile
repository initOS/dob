ARG PYTHON_VERSION

FROM python:${PYTHON_VERSION}-slim AS base

ADD odoo/apt.txt /srv/odoo/apt.txt

ENV GIT_AUTHOR_NAME=odoo
ENV GIT_COMMITTER_NAME=odoo
ENV EMAIL=dob

ARG WKHTMLTOPDF_VERSION=0.12.6.1-3
ARG WKHTMLTOPDF_CHECKSUM='98ba0d157b50d36f23bd0dedf4c0aa28c7b0c50fcdcdc54aa5b6bbba81a3941d'

RUN apt-get update && \
  export DEBIAN_FRONTEND=noninteractive && \
  cat /srv/odoo/apt.txt | xargs apt-get install --no-install-recommends -yqq && \
  curl -SLo wkhtmltox.deb https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_VERSION}/wkhtmltox_${WKHTMLTOPDF_VERSION}.bookworm_amd64.deb && \
  echo "${WKHTMLTOPDF_CHECKSUM}  wkhtmltox.deb" | sha256sum -c - && \
  apt-get install -yqq --no-install-recommends ./wkhtmltox.deb && \
  rm wkhtmltox.deb && \
  wkhtmltopdf --version && \
  rm -rf /var/lib/apt/lists/*

ARG UID=1000
ARG GID=1000

RUN groupadd -g $GID odoo -o && \
    useradd -l -md /srv/odoo -s /bin/false -u $UID -g $GID odoo && \
    chown -R odoo:odoo /srv/odoo &&\
    sync

ADD odoo/npm.txt /srv/odoo/npm.txt
RUN cat /srv/odoo/npm.txt | xargs npm install --global

ADD odoo/requirements.txt odoo/versions.txt* /srv/odoo/
RUN if [ -r '/srv/odoo/versions.txt' ]; \
        then python3 -m pip install --no-cache-dir -r /srv/odoo/versions.txt; \
    fi

RUN python3 -m pip install --no-cache-dir -r /srv/odoo/requirements.txt

COPY bin/* /usr/local/bin/

EXPOSE 8069 8072

CMD ["odoo", "run"]

# Copy everything into the image for an automatic deployment
FROM base AS deploy
COPY --chown=odoo:odoo odoo/*.yaml /srv/odoo/odoo/
COPY --chown=odoo:odoo odoo/src /srv/odoo/odoo/src/

USER odoo
WORKDIR /srv/odoo/odoo

RUN mkdir -p -m 0700 /srv/odoo/.ssh && \
  ssh-keyscan -H github.com >> /srv/odoo/.ssh/known_hosts && \
  ssh-keyscan -H git.initos.com >> /srv/odoo/.ssh/known_hosts

# Set up SSH keys and initialize the repositories
RUN --mount=type=ssh,uid=$UID ls -la /srv/odoo/ && odoo -c odoo.project.yaml init
