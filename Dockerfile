FROM ubuntu:focal

ADD odoo/apt.txt /srv/odoo/apt.txt

ARG WKHTMLTOPDF_VERSION=0.12.5
ARG WKHTMLTOPDF_CHECKSUM='db48fa1a043309c4bfe8c8e0e38dc06c183f821599dd88d4e3cea47c5a5d4cd3'

RUN apt-get update && \
  export DEBIAN_FRONTEND=noninteractive && \
  cat /srv/odoo/apt.txt | xargs apt-get install --no-install-recommends -yqq && \
  curl -SLo wkhtmltox.deb https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/${WKHTMLTOPDF_VERSION}/wkhtmltox_${WKHTMLTOPDF_VERSION}-1.bionic_amd64.deb && \
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

ADD odoo/requirements.txt /srv/odoo/requirements.txt
ADD odoo/versions.txt /srv/odoo/versions.txt
RUN python3 -m pip install --no-cache-dir -r /srv/odoo/requirements.txt -r /srv/odoo/versions.txt


COPY bin/* /usr/local/bin/

EXPOSE 8069 8072

CMD ["odoo", "run"]
