# pylint: disable=broad-except, unspecified-encoding
# pylint: disable=no-member, too-few-public-methods
"""
 ╔╗ ┬┌┬┐┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐  ╔╦╗┌─┐─┐ ┬  ╦ ╦─┐ ┬
 ╠╩╗│ │ └─┐├─┤├─┤├┬┘├┤ └─┐   ║║├┤ ┌┴┬┘  ║ ║┌┴┬┘
 ╚═╝┴ ┴ └─┘┴ ┴┴ ┴┴└─└─┘└─┘  ═╩╝└─┘┴ └─  ╚═╝┴ └─
Bitshares Decentralized Exchange User Experience

Add resource endpoints to falcon App
Run with
`uvicorn falcon_website:APP`
or similar hosting engine
"""
# STANDARD MOUDLES
import os
import traceback

# THIRD PARTY MODULES
import falcon
import falcon.asgi

from config import DEFAULT_PAIR

# BITSHARES DEX UX MODULES
from utilities import it


class FileResource:
    """
    Serve a static file, including HTML, JavaScript, CSS, and text files.
    The content type of the response is automatically determined based on the extension.
    Additionally, the resource can be customized for specific HTML pages
    with placeholder values for data such as pair, currency, asset, and contract.
    """

    def __init__(self, filen):
        """
        Initialize the class with the file name to be served.

        Parameters:
        filen (str): The name of the file to be served.
        """
        self.resource = filen

    async def on_get(self, req, resp):
        """
        Handle GET requests by sending the contents of the file
        specified in `self.resource` in the response.

        :param req: The request object from Falcon.
        :type req: falcon.Request
        :param resp: The response object from Falcon.
        :type resp: falcon.Response
        """
        req_params = {k.strip("?'\"&"): v.strip("?'\"&") for k, v in req.params.items()}

        try:
            # Set the response content type based on the file extension.
            if self.resource.endswith(".html"):
                resp.content_type = falcon.MEDIA_HTML
            elif self.resource.endswith(".js"):
                resp.content_type = falcon.MEDIA_JS
            elif self.resource.endswith("css"):
                resp.content_type = "text/css"
            else:
                resp.content_type = "text/plain"

            # Open the file, read its contents, and close it.
            with open(
                self.resource, "r" if resp.content_type != "text/plain" else "rb"
            ) as handle:
                data = handle.read()

            # If the file is "order_book.html", replace placeholder values in the file with values from the request params.
            if self.resource == "order_book.html":
                data = data.replace(
                    "<<<pair>>>",
                    req_params.get("pair", DEFAULT_PAIR)
                    .replace("_", ":")
                    .strip("?'\"&"),
                )
                data = data.replace(
                    "<<<currency>>>",
                    req_params.get("pair", DEFAULT_PAIR)
                    .replace("_", ":")
                    .split(":")[1]
                    .strip("?'\"&"),
                )
                data = data.replace(
                    "<<<asset>>>",
                    req_params.get("pair", DEFAULT_PAIR)
                    .replace("_", ":")
                    .split(":")[0]
                    .strip("?'\"&"),
                )
                data = data.replace(
                    "<<<contract>>>", req_params.get("contract", "1.0.0").strip("?'\"&")
                )

            # Set the response text and log the result.
            resp.text = data
            print(it("green", "INFO: ") + f"{self.resource.ljust(50)} 200")
            resp.status = falcon.HTTP_200

        except Exception:
            print(it("red", "ERROR: ") + f"{self.resource.ljust(50)} 500")
            resp.status = falcon.HTTP_500
            traceback.print_exc()


assets = []
for path, currentDirectory, files in os.walk("assets/"):
    assets.extend(f"/{os.path.join(path, file)}" for file in files)
print("\033c")
ui = falcon.asgi.App()
ui.add_route("/exchange.html", FileResource("order_book.html"))
ui.add_route("/index.html", FileResource("landing.html"))
ui.add_route("/main.js", FileResource("main.js"))
ui.add_route("/buttons.css", FileResource("buttons.css"))
ui.add_route("/barchart.css", FileResource("barchart.css"))
for asset in assets:
    # print(asset)
    ui.add_route(asset, FileResource(asset[1:]))
